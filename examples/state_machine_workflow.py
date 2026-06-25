"""
Worked example for Pattern #13 — State machine / workflow graph.

Open-ended loops are useful while exploring, but production agents need sharper
phase boundaries. A workflow graph makes those boundaries explicit: each state
has allowed tools, required data, and a narrow reason to transition.

This demo runs a tiny support-style workflow:

    triage -> plan -> act -> verify -> finish
                         -> escalate

No SDK, no network, no API key. The fake tools are plain Python functions so the
control flow stays visible.

    python examples/state_machine_workflow.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

State = Literal["triage", "plan", "act", "verify", "finish", "escalate"]
ToolName = Literal["classify", "draft_steps", "lookup_order", "send_reply", "verify_reply"]

ALLOWED_TOOLS: dict[State, set[ToolName]] = {
    "triage": {"classify"},
    "plan": {"draft_steps"},
    "act": {"lookup_order"},
    "verify": {"verify_reply"},
    "finish": {"send_reply"},
    "escalate": set(),
}


@dataclass
class WorkflowContext:
    ticket: str
    state: State = "triage"
    category: str | None = None
    plan: list[str] = field(default_factory=list)
    order_status: str | None = None
    reply: str | None = None
    transition_log: list[str] = field(default_factory=list)

    def move(self, next_state: State, reason: str) -> None:
        self.transition_log.append(f"{self.state} -> {next_state}: {reason}")
        self.state = next_state


def require_tool(ctx: WorkflowContext, tool: ToolName) -> None:
    if tool not in ALLOWED_TOOLS[ctx.state]:
        allowed = ", ".join(sorted(ALLOWED_TOOLS[ctx.state])) or "no tools"
        raise RuntimeError(f"{tool!r} is not allowed in {ctx.state!r}; allowed: {allowed}")


def classify(ctx: WorkflowContext) -> str:
    require_tool(ctx, "classify")
    lowered = ctx.ticket.lower()
    if "refund" in lowered or "chargeback" in lowered:
        return "billing-risk"
    if "order" in lowered or "shipment" in lowered:
        return "order-status"
    return "general"


def draft_steps(ctx: WorkflowContext) -> list[str]:
    require_tool(ctx, "draft_steps")
    if ctx.category == "order-status":
        return ["look up order", "draft concise status reply", "verify reply before send"]
    return ["escalate to a human owner"]


def lookup_order(ctx: WorkflowContext) -> str:
    require_tool(ctx, "lookup_order")
    # Stand-in for a CRM, database, or shipping API call.
    return "shipped yesterday; tracking link is available in the customer portal"


def verify_reply(ctx: WorkflowContext) -> tuple[bool, str]:
    require_tool(ctx, "verify_reply")
    if not ctx.reply:
        return False, "reply is missing"
    if "guaranteed" in ctx.reply.lower():
        return False, "reply makes an unsafe guarantee"
    if len(ctx.reply) > 280:
        return False, "reply is too long for this channel"
    return True, "reply satisfies the contract"


def send_reply(ctx: WorkflowContext) -> None:
    require_tool(ctx, "send_reply")
    print("SENT:")
    print(ctx.reply)


HANDLERS: dict[State, Callable[[WorkflowContext], None]] = {}


def handler(state: State) -> Callable[[Callable[[WorkflowContext], None]], Callable[[WorkflowContext], None]]:
    def register(fn: Callable[[WorkflowContext], None]) -> Callable[[WorkflowContext], None]:
        HANDLERS[state] = fn
        return fn

    return register


@handler("triage")
def triage(ctx: WorkflowContext) -> None:
    ctx.category = classify(ctx)
    if ctx.category == "billing-risk":
        ctx.move("escalate", "billing-risk tickets need human approval")
    else:
        ctx.move("plan", f"classified as {ctx.category}")


@handler("plan")
def plan(ctx: WorkflowContext) -> None:
    ctx.plan = draft_steps(ctx)
    if ctx.plan == ["escalate to a human owner"]:
        ctx.move("escalate", "no safe automated path")
    else:
        ctx.move("act", "plan has a safe lookup step")


@handler("act")
def act(ctx: WorkflowContext) -> None:
    ctx.order_status = lookup_order(ctx)
    ctx.reply = f"Thanks for checking in. Your order {ctx.order_status}."
    ctx.move("verify", "drafted reply from order lookup")


@handler("verify")
def verify(ctx: WorkflowContext) -> None:
    ok, reason = verify_reply(ctx)
    ctx.move("finish" if ok else "escalate", reason)


@handler("finish")
def finish(ctx: WorkflowContext) -> None:
    send_reply(ctx)


@handler("escalate")
def escalate(ctx: WorkflowContext) -> None:
    print("ESCALATED:")
    print(ctx.ticket)


def run(ticket: str) -> WorkflowContext:
    ctx = WorkflowContext(ticket=ticket)

    while ctx.state not in {"finish", "escalate"}:
        HANDLERS[ctx.state](ctx)

    HANDLERS[ctx.state](ctx)
    return ctx


def main() -> None:
    for ticket in (
        "Can you check whether my order has shipped?",
        "I want a refund before I file a chargeback.",
    ):
        print("=" * 72)
        ctx = run(ticket)
        print("\nTRANSITIONS:")
        for event in ctx.transition_log:
            print(f"- {event}")
        print()


if __name__ == "__main__":
    main()
