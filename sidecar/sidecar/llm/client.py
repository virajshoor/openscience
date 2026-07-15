"""OpenAI-compatible LLM client with streaming, tool dispatch, and ReAct fallback."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, List, Optional

import httpx

from ..http import async_client
from .react import parse_react, ReActStep, REACT_SYSTEM_PROMPT
from .reviewer import Reviewer


@dataclass
class LLMConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    use_tools: bool = True


class LLMClient:
    """Thin wrapper over /v1/chat/completions using httpx for streaming."""

    def __init__(self) -> None:
        self.reviewer = Reviewer(self)
        self._client: Optional[httpx.AsyncClient] = None

    async def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = async_client(httpx.Timeout(300.0, connect=30.0))
        return self._client

    async def _post(
        self, config: dict, messages: list, tools: list | None = None, stream: bool = True
    ) -> httpx.Response:
        cfg = {
            "base_url": config.get("base_url", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")),
            "api_key": str(config.get("api_key", os.environ.get("OPENAI_API_KEY", "")) or "").strip(),
            "model": config.get("model", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")),
            "temperature": float(config.get("temperature", 0.2)),
        }
        url = cfg["base_url"].rstrip("/") + "/chat/completions"
        body: dict = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": cfg["temperature"],
            "stream": stream,
        }
        if tools and config.get("use_tools", True):
            body["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        client = await self.client()
        return await client.post(url, json=body, headers=headers, timeout=None)

    async def _stream_post(self, config: dict, messages: list, tools: list | None = None) -> httpx.Response:
        cfg = {
            "base_url": config.get("base_url", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")),
            "api_key": str(config.get("api_key", os.environ.get("OPENAI_API_KEY", "")) or "").strip(),
            "model": config.get("model", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")),
            "temperature": float(config.get("temperature", 0.2)),
        }
        body: dict = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": cfg["temperature"],
            "stream": True,
        }
        if tools and config.get("use_tools", True):
            body["tools"] = tools
        client = await self.client()
        headers = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        request = client.build_request(
            "POST",
            cfg["base_url"].rstrip("/") + "/chat/completions",
            json=body,
            headers=headers,
        )
        return await client.send(request, stream=True)

    async def run(
        self,
        messages: list,
        config: dict,
        tools: Any,
        backend: Any,
        recorder: Any,
    ) -> AsyncIterator[dict]:
        """Main agentic loop. Yields SSE event dicts with JSON-serializable data."""
        run_id = recorder.start(config)
        conv: List[dict] = [dict(m) for m in messages]
        # If not using native tool-calling, inject ReAct system prompt
        if not config.get("use_tools", True) and conv and conv[0].get("role") != "system":
            tool_descs = "\n".join(
                f"  - {name}: {t.description}" for name, t in tools.items()
            )
            conv.insert(0, {"role": "system", "content": REACT_SYSTEM_PROMPT.format(tool_descriptions=tool_descs)})
        # Build tool schemas, converting dotted names to underscores (OpenAI requires ^[a-zA-Z0-9_-]+$)
        tool_schemas = []
        name_map = {}  # underscore_name -> dotted_name
        for name, t in tools.items():
            safe_name = name.replace(".", "_")
            schema = t.schema()["openai"]
            schema["function"]["name"] = safe_name
            tool_schemas.append(schema)
            name_map[safe_name] = name
        max_iters = 12

        for _ in range(max_iters):
            try:
                resp = await self._stream_post(config, conv, tools=tool_schemas)
            except Exception as e:
                yield {"event": "error", "data": {"message": str(e)}}
                break

            if resp.status_code != 200:
                err_text = (await resp.aread()).decode(errors="replace")[:500]
                await resp.aclose()
                yield {"event": "error", "data": {"message": f"LLM {resp.status_code}: {err_text}"}}
                break

            assistant_msg: dict = {}
            async for event in self._consume_stream(resp):
                if event["event"] == "assistant":
                    assistant_msg = event["data"]
                else:
                    yield event
            await resp.aclose()

            conv.append(assistant_msg)
            recorder.append(run_id, "assistant", assistant_msg)

            tool_calls = assistant_msg.get("tool_calls") or []

            # ReAct fallback for endpoints without tool-calling
            if not tool_calls and not config.get("use_tools", True):
                react_steps = parse_react(assistant_msg.get("content", ""))
                if not react_steps:
                    recorder.finish(run_id)
                    break
                tool_calls = self._react_to_tool_calls(react_steps)

            # Also try ReAct when tools were offered but model didn't use them
            if not tool_calls:
                react_steps = parse_react(assistant_msg.get("content", ""))
                if react_steps:
                    tool_calls = self._react_to_tool_calls(react_steps)

            if not tool_calls:
                recorder.finish(run_id)
                break

            # Execute tool calls
            for tc in tool_calls:
                fn = tc["function"]
                tool_name = fn["name"]
                # Map underscore name back to dotted name
                tool_name = name_map.get(tool_name, tool_name)
                try:
                    args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                except json.JSONDecodeError:
                    args = {}
                yield {"event": "tool_call", "data": {"id": tc["id"], "name": tool_name, "arguments": args}}

                tool = tools.get(tool_name)
                if tool is None:
                    result = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        result = await tool.invoke(args, backend=backend, recorder=recorder, run_id=run_id)
                    except Exception as e:
                        result = {"error": str(e)}

                yield {"event": "tool_result", "data": {"id": tc["id"], "name": tool_name, "result": result}}

                # If tool produced a viewer artifact, emit it
                viewer = result.get("viewer") if isinstance(result, dict) else None
                if viewer:
                    yield {"event": "viewer", "data": viewer}
                # A tool may emit several viewers (e.g. code.run with multiple figures)
                viewers = result.get("viewers") if isinstance(result, dict) else None
                if isinstance(viewers, list):
                    for v in viewers:
                        if isinstance(v, dict) and v.get("type"):
                            yield {"event": "viewer", "data": v}

                conv.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": json.dumps(result.get("summary", result), default=str)[:4000],
                    }
                )
                recorder.append(run_id, "tool", {"tool": tool_name, "args": args, "result": result})

                if isinstance(result, dict) and result.get("error"):
                    message = f"I couldn't complete {tool_name}: {result['error']}."
                    assistant_error = {"role": "assistant", "content": message}
                    conv.append(assistant_error)
                    recorder.append(run_id, "assistant", assistant_error)
                    yield {"event": "token", "data": {"text": message}}
                    recorder.finish(run_id)
                    break
            else:
                continue
            break
        else:
            yield {"event": "error", "data": {"message": "Max iterations reached"}}
            recorder.finish(run_id)

        yield {"event": "done", "data": {"run_id": run_id}}

    @staticmethod
    def _react_to_tool_calls(steps: List[ReActStep]) -> list[dict]:
        return [
            {
                "id": f"react-{i}",
                "type": "function",
                "function": {
                    "name": s.action,
                    "arguments": json.dumps(s.input),
                },
            }
            for i, s in enumerate(steps)
        ]

    async def _consume_stream(self, resp: httpx.Response) -> AsyncIterator[dict]:
        """Consume an upstream SSE stream while yielding content deltas immediately."""
        assistant: dict = {"role": "assistant", "content": ""}
        tool_calls: dict[int, dict] = {}

        async for line in resp.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {})
                if delta.get("content"):
                    assistant["content"] += delta["content"]
                    yield {"event": "token", "data": {"text": delta["content"]}}
                if delta.get("tool_calls"):
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls:
                            tool_calls[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                        if tc.get("id"):
                            tool_calls[idx]["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            tool_calls[idx]["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            tool_calls[idx]["function"]["arguments"] += fn["arguments"]

        if tool_calls:
            assistant["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
        yield {"event": "assistant", "data": assistant}
