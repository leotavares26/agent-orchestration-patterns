"""
Worked example for Pattern #11 — Verifier gate.

A verifier gate keeps the worker's *draft* separate from the side effect. The
worker can be creative, but only a verified output is allowed to leave the
sandbox.

This tiny example pretends an agent is drafting a customer-status update. Before
we "send" it, an independent verifier checks a concrete contract:

    - required fields are present
    - the message is short enough
    - no banned promise or unsafe phrasing is included

No LLM SDK, no network, no API key. The point is the control flow: draft first,
verify second, perform the side effect last.

    python examples/verifier_gate.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Draft:
    """What the worker produced. Treat this as untrusted until verified."""

    subject: str
    body: str
    audience: str = "customer"


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def verify_customer_update(
    draft: Draft,
    *,
    max_body_chars: int = 240,
    banned_phrases: Iterable[str] = ("guaranteed", "refund approved", "delete your data"),
) -> VerificationResult:
    """Independent contract check before any irreversible action happens."""
    reasons: list[str] = []

    if draft.audience != "customer":
        reasons.append("audience must be 'customer'")

    if not draft.subject.strip():
        reasons.append("subject is required")

    if not draft.body.strip():
        reasons.append("body is required")

    if len(draft.body) > max_body_chars:
        reasons.append(f"body is too long ({len(draft.body)} > {max_body_chars} chars)")

    lowered_body = draft.body.lower()
    for phrase in banned_phrases:
        if phrase in lowered_body:
            reasons.append(f"banned phrase: {phrase!r}")

    return VerificationResult(ok=not reasons, reasons=reasons)


def send_customer_update(draft: Draft) -> None:
    """The side effect. In production this might call Gmail, Zendesk, or Slack."""
    print(f"SENT: {draft.subject}\n{draft.body}")


def run_with_verifier_gate(draft: Draft) -> None:
    result = verify_customer_update(draft)

    if not result.ok:
        print("BLOCKED:")
        for reason in result.reasons:
            print(f"  - {reason}")
        print("Route back to the worker for repair, or escalate to a human.\n")
        return

    send_customer_update(draft)
    print("Verified first, side effect second.\n")


def main() -> None:
    good_draft = Draft(
        subject="Status update on your import",
        body="The import finished successfully. I checked the row count and spot-checked the output, so you can continue with the next step.",
    )

    risky_draft = Draft(
        subject="Status update on your import",
        body="Your import is guaranteed to be correct, and the refund approved if anything looks off.",
    )

    print("1) valid draft passes the gate:")
    run_with_verifier_gate(good_draft)

    print("2) risky draft is blocked before sending:")
    run_with_verifier_gate(risky_draft)


if __name__ == "__main__":
    main()
