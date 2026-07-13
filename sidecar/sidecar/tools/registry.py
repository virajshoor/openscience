"""Tool registry. Tools are async functions decorated with @tool(name, description).

Each tool receives args, and keyword-only: backend, recorder, run_id.
A tool returns a dict with:
  - summary: short text for the LLM
  - viewer (optional): a dict {type, src} telling the UI what to render
  - data (optional): raw structured data
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass
class Tool:
    name: str
    description: str
    params: dict  # JSON schema for the function parameters
    func: Callable

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "openai": {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": self.params,
                },
            },
        }

    async def invoke(self, args: dict, *, backend, recorder, run_id) -> Any:
        sig = inspect.signature(self.func)
        kw = {}
        for p in sig.parameters.values():
            if p.name in args:
                kw[p.name] = args[p.name]
        # Always allow these as kwargs if the function accepts them
        for extra in ("backend", "recorder", "run_id"):
            if extra in sig.parameters:
                kw[extra] = {"backend": backend, "recorder": recorder, "run_id": run_id}[extra]
        result = self.func(**kw)
        if inspect.isawaitable(result):
            result = await result
        return result


class _Registry:
    def __init__(self) -> None:
        self.tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str, params: dict) -> Callable:
        def deco(func: Callable) -> Callable:
            self.tools[name] = Tool(name=name, description=description, params=params, func=func)
            return func
        return deco


registry = _Registry()
tool = registry.register