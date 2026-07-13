"""
Worked example for Pattern #6 — Human-in-the-loop.

Some actions are irreversible or high-stakes: sending money, deleting data,
emailing a customer. For those, the agent should not act on its own confidence.
It pauses at a checkpoint, hands a human a clear summary of what it wants to do,
and only proceeds once it has explicit approval.

The interesting design question is *which* actions need a human. Gating
everything adds friction with no payoff; gating nothing is how an agent wires
money to the wrong account at 2am. So this example routes on two axes the agent
can actually reason about — is the action reversible, and how large is the blast
radius — and only stops for the ones that clear a threshold.

No LLM SDK, no network, no API key. The approval step is faked with a callback so
the file runs unattended; in production, swap it for a Slack button, an email
reply, or a review queue.

    python examples/human_in_the_loop.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class Decision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class Action:
    """A side effect the agent wants to perform."""

    name: str
    summary: str
    reversible: bool
    # Rough blast radius: how many people/records this touches if it goes wrong.
    blast_radius: int


@dataclass(frozen=True)
class Outcome:
    performed: bool
    detail: str


# An approver takes the pending action and returns a decision. In production this
# is a human on the other side of Slack, email, or a review UI. Here it is a
# plain callback so the example runs on its own.
Approver = Callable[[Action], Decision]


def needs_approval(action: Action, *, blast_radius_limit: int = 5) -> bool:
    """Gate only the actions that actually warrant a human.

    Cheap, reversible, small-blast actions run straight through. An action stops
    for a human if undoing it is hard *or* it touches more than we are willing to
    let the agent decide alone.
    """
    if not action.reversible:
        return True
    return action.blast_radius > blast_radius_limit


def perform(action: Action) -> Outcome:
    """The actual side effect. Reached only after any required approval."""
    return Outcome(performed=True, detail=f"performed: {action.name}")


def run_with_checkpoint(action: Action, approve: Approver) -> Outcome:
    if not needs_approval(action):
        # Low-stakes: act without stopping. Friction with no payoff is a cost too.
        return perform(action)

    # High-stakes: pause and hand the human a concrete summary to decide on.
    print(f"CHECKPOINT — approval needed for: {action.name}")
    print(f"  what:       {action.summary}")
    print(f"  reversible: {action.reversible}")
    print(f"  blast:      {action.blast_radius}")

    decision = approve(action)

    if decision is Decision.APPROVE:
        outcome = perform(action)
        print(f"  APPROVED -> {outcome.detail}\n")
        return outcome

    print("  REJECTED -> action skipped; route back to the agent or escalate.\n")
    return Outcome(performed=False, detail=f"rejected: {action.name}")


def main() -> None:
    # Stand-ins for a real human. auto_approve/auto_reject keep the file runnable.
    auto_approve: Approver = lambda _action: Decision.APPROVE
    auto_reject: Approver = lambda _action: Decision.REJECT

    tag_ticket = Action(
        name="tag_ticket",
        summary="Add the label 'billing' to support ticket #4821.",
        reversible=True,
        blast_radius=1,
    )
    refund_customer = Action(
        name="refund_customer",
        summary="Issue a $2,400 refund to customer #77.",
        reversible=False,
        blast_radius=1,
    )
    email_all_users = Action(
        name="email_all_users",
        summary="Send a service-status email to all 9,000 users.",
        reversible=False,
        blast_radius=9000,
    )

    print("1) low-stakes action runs without a checkpoint:")
    outcome = run_with_checkpoint(tag_ticket, auto_reject)
    print(f"   -> {outcome.detail}\n")

    print("2) irreversible action pauses for approval (human approves):")
    run_with_checkpoint(refund_customer, auto_approve)

    print("3) large-blast action pauses for approval (human rejects):")
    run_with_checkpoint(email_all_users, auto_reject)


if __name__ == "__main__":
    main()
