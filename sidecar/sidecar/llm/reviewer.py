"""Automated reviewer.

A second LLM pass that fact-checks an existing run:
  - Every numeric claim should trace to a tool output.
  - Every citation should appear verbatim in a tool result.

Produces a verdict (pass/flag/fail) with a list of issues, written to review.json
in the run directory.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

REVIEW_SYSTEM = """You are an automated scientific reviewer. You are given a research conversation that
included tool calls. Your job is to verify the assistant's final claims.

For each claim:
  - If the claim is a number, check it appears in a tool result.
  - If the claim is a citation or accession ID, check it appears in a tool result.
  - If the claim is a code-derived result, check the code output.

Output JSON only:
{
  "verdict": "pass" | "flag" | "fail",
  "issues": [{"claim": "...", "evidence": "missing" | "contradicted", "detail": "..."}],
  "summary": "one-line summary"
}
"""


class Reviewer:
    def __init__(self, llm) -> None:
        self.llm = llm

    async def review(self, run_id: str, recorder, config: dict) -> dict:
        run = recorder.read_run(run_id)
        if not run:
            return {"error": "run not found"}
        transcript = self._transcript(run)
        prompt = (
            "Conversation transcript (with tool calls and results):\n\n"
            + transcript
            + "\n\nNow produce your review JSON."
        )
        cfg = {**config, "use_tools": False, "temperature": 0.0}
        try:
            resp = await self.llm._post(
                cfg,
                [{"role": "system", "content": REVIEW_SYSTEM}, {"role": "user", "content": prompt}],
                tools=None,
                stream=False,
            )
            if resp.status_code != 200:
                return {"error": f"reviewer LLM {resp.status_code}"}
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            verdict = self._parse_verdict(content)
        except Exception as e:
            verdict = {"verdict": "error", "issues": [], "summary": str(e)}
        recorder.write_review(run_id, verdict)
        return verdict

    def _transcript(self, run: dict) -> str:
        lines = []
        for entry in run.get("conversation", []):
            role = entry["role"]
            if role == "assistant":
                msg = entry["message"]
                content = msg.get("content", "")
                if content:
                    lines.append(f"ASSISTANT: {content}")
                for tc in msg.get("tool_calls", []) or []:
                    fn = tc.get("function", {})
                    lines.append(f"  [tool_call {fn.get('name')}] args={fn.get('arguments')}")
            elif role == "tool":
                lines.append(f"  [tool_result {entry['tool']}] {json.dumps(entry['result'], default=str)[:1500]}")
            elif role == "user":
                lines.append(f"USER: {entry['message']['content']}")
        return "\n\n".join(lines)

    def _parse_verdict(self, text: str) -> dict:
        # Extract first JSON object from the text
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {"verdict": "flag", "issues": [], "summary": "reviewer returned no parseable JSON"}
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"verdict": "flag", "issues": [], "summary": "reviewer returned unparseable JSON"}