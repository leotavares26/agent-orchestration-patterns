"""
Worked example for Pattern #7 — Tool-use guardrails.

An agent should not be able to call every tool in every state. This example keeps
three boring but load-bearing checks in front of the dispatcher:

    - state allowlist: is this tool allowed right now?
    - argument schema: are required fields present and typed correctly?
    - side-effect policy: is a human approval flag present for risky sends?

No SDK, no network, no API key. The point is the seam: validate the proposed tool
call before executing it, and return an error the agent can actually repair.

    python examples/tool_guardrails.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolCall:
    """A model-proposed tool call. Treat it as untrusted input."""

    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    """The minimum contract a dispatcher should know before calling a tool."""

    required_args: dict[str, type]
    handler: Callable[[dict[str, Any]], str]
    requires_approval: bool = False


TOOLS: dict[str, ToolSpec] = {
    "search_docs": ToolSpec(
        required_args={"query": str},
        handler=lambda args: f"searched docs for {args['query']!r}",
    ),
    "send_status_update": ToolSpec(
        required_args={"recipient": str, "body": str},
        handler=lambda args: f"sent update to {args['recipient']}",
        requires_approval=True,
    ),
}

ALLOWED_BY_STATE: dict[str, set[str]] = {
    "research": {"search_docs"},
    "review": {"search_docs"},
    "send": {"send_status_update"},
}


def validate_tool_call(call: ToolCall, *, state: str, approved: bool = False) -> list[str]:
    """Return repairable errors instead of letting bad calls hit real tools."""
    errors: list[str] = []

    spec = TOOLS.get(call.name)
    if spec is None:
        return [f"unknown tool: {call.name!r}"]

    allowed_tools = ALLOWED_BY_STATE.get(state, set())
    if call.name not in allowed_tools:
        errors.append(f"tool {call.name!r} is not allowed in state {state!r}")

    for arg_name, arg_type in spec.required_args.items():
        if arg_name not in call.args:
            errors.append(f"missing required argument: {arg_name}")
        elif not isinstance(call.args[arg_name], arg_type):
            expected = arg_type.__name__
            actual = type(call.args[arg_name]).__name__
            errors.append(f"argument {arg_name!r} must be {expected}, got {actual}")

    unknown_args = sorted(set(call.args) - set(spec.required_args))
    if unknown_args:
        errors.append(f"unknown arguments: {', '.join(unknown_args)}")

    if spec.requires_approval and not approved:
        errors.append(f"tool {call.name!r} requires human approval")

    return errors


def dispatch(call: ToolCall, *, state: str, approved: bool = False) -> str:
    errors = validate_tool_call(call, state=state, approved=approved)
    if errors:
        return "BLOCKED:\n" + "\n".join(f"  - {error}" for error in errors)

    return TOOLS[call.name].handler(call.args)


def main() -> None:
    examples = [
        ("good research call", ToolCall("search_docs", {"query": "retry budgets"}), "research", False),
        ("wrong state", ToolCall("send_status_update", {"recipient": "team@example.com", "body": "Done"}), "research", True),
        ("missing approval", ToolCall("send_status_update", {"recipient": "team@example.com", "body": "Done"}), "send", False),
        ("approved send", ToolCall("send_status_update", {"recipient": "team@example.com", "body": "Done"}), "send", True),
    ]

    for label, call, state, approved in examples:
        print(f"{label}:")
        print(dispatch(call, state=state, approved=approved))
        print()


if __name__ == "__main__":
    main()
