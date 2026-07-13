"""ReAct text-loop parser. Fallback for endpoints without native tool-calling.

We prompt the model to emit a JSON action block:

  Thought: I should fetch the UniProt entry.
  Action: {"tool": "uniprot.fetch", "input": {"accession": "P12345"}}

The parser extracts the Action JSON and returns a list of ReActStep objects.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class ReActStep:
    thought: str
    action: str
    input: dict


_ACTION_RE = re.compile(r"Action:\s*```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_ACTION_RE_LOOSE = re.compile(r"Action:\s*(\{.*\})", re.DOTALL)
_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=Action:|$)", re.DOTALL)


def parse_react(text: str) -> List[ReActStep]:
    """Extract ReAct steps from assistant text. Returns [] if none found."""
    if not text or "Action:" not in text:
        return []
    steps: List[ReActStep] = []
    # Split on "Thought:" markers to handle multiple steps
    blocks = re.split(r"(?=Thought:)", text)
    for block in blocks:
        thought_m = _THOUGHT_RE.search(block)
        thought = thought_m.group(1).strip() if thought_m else ""
        action_json: Optional[str] = None
        m = _ACTION_RE.search(block)
        if m:
            action_json = m.group(1)
        else:
            m = _ACTION_RE_LOOSE.search(block)
            if m:
                action_json = m.group(1)
        if not action_json:
            continue
        try:
            parsed = json.loads(action_json)
        except json.JSONDecodeError:
            continue
        tool = parsed.get("tool") or parsed.get("action") or parsed.get("name")
        inp = parsed.get("input") or parsed.get("args") or {}
        if not tool:
            continue
        if isinstance(inp, str):
            try:
                inp = json.loads(inp)
            except json.JSONDecodeError:
                inp = {"value": inp}
        steps.append(ReActStep(thought=thought, action=tool, input=inp if isinstance(inp, dict) else {"value": inp}))
    return steps


REACT_SYSTEM_PROMPT = """You are a scientific research assistant. You have access to tools.

When you want to use a tool, respond with EXACTLY this format:

Thought: <your reasoning>
Action: ```json
{"tool": "<tool_name>", "input": {<arguments>}}
```

After the tool result is returned, you may continue reasoning or give a final answer.
When you have the final answer and do not need any tool, respond normally without "Action:".

Available tools:
{tool_descriptions}
"""