"""Evidence ledger: what the agent actually retrieved during one investigation.

Filled by a function middleware (works for in-process and MCP tools alike). The Reviewer
and the eval harness use it to check that every cited record and policy section was really
fetched — the basis of the "no invented evidence" guarantee.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agent_framework import FunctionInvocationContext, function_middleware


@dataclass
class ToolCall:
    name: str
    arguments: dict
    output: Any
    error: str | None = None


@dataclass
class Ledger:
    calls: list[ToolCall] = field(default_factory=list)
    records: set[str] = field(default_factory=set)
    policy_sections: set[str] = field(default_factory=set)
    injection_flags: set[str] = field(default_factory=set)

    def add(self, name: str, arguments: dict, output: Any, error: str | None = None) -> None:
        self.calls.append(ToolCall(name, arguments, output, error))
        if isinstance(output, dict):
            self.records.update(output.get("records", []))
            for hit in output.get("results", []) if name == "search_policy" else []:
                self.policy_sections.add(hit["section_id"])
            _collect_flags(output, self.injection_flags)

    @property
    def tool_names(self) -> list[str]:
        return [c.name for c in self.calls]


def _collect_flags(obj: Any, acc: set[str]) -> None:
    if isinstance(obj, dict):
        if obj.get("suspicious"):
            acc.update(obj.get("injection_flags", []))
        for v in obj.values():
            _collect_flags(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_flags(v, acc)


def _as_json(result: Any) -> Any:
    """Tool results arrive as framework Content items (or raw values); normalise to Python."""
    if isinstance(result, list) and result and hasattr(result[0], "type"):
        texts = [getattr(c, "text", None) or getattr(c, "result", None) for c in result]
        result = texts[0] if len(texts) == 1 else texts
    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            return result
    return result


def ledger_middleware(ledger: Ledger):
    """Function middleware that records every tool call of one investigation into `ledger`."""

    @function_middleware
    async def _record(context: FunctionInvocationContext, call_next) -> None:
        args = context.arguments
        args = args.model_dump() if hasattr(args, "model_dump") else dict(args or {})
        try:
            await call_next()
        except Exception as exc:  # recorded, then re-raised so the framework reports it to the model
            ledger.add(context.function.name, args, None, error=f"{type(exc).__name__}: {exc}")
            raise
        ledger.add(context.function.name, args, _as_json(context.result))

    return _record
