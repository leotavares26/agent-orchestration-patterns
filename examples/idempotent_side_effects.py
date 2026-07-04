"""
Worked example for Pattern #14 — Idempotent side effects.

Retries are necessary, but retrying an external write can duplicate the thing you
were trying to protect: two emails, two tickets, two charges, two PR comments.
The fix is to turn every write into an idempotent command with a stable
operation ID and a durable record of the result.

This demo pretends an agent is creating support tickets. The first call writes
the ticket, records the result, then the caller loses the response. A retry with
the same operation ID returns the original ticket instead of creating a
duplicate.

    python examples/idempotent_side_effects.py

No SDK, no network, no API keys. The "ticket system" and idempotency store are
plain dictionaries so the control flow is the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class TicketCommand:
    """A side effect request with a stable dedupe key."""

    operation_id: str
    title: str
    customer_id: str


@dataclass(frozen=True)
class TicketResult:
    ticket_id: str
    title: str
    customer_id: str
    created: bool


@dataclass
class FakeTicketSystem:
    """A stand-in for Zendesk, Linear, GitHub Issues, or another write API."""

    tickets: dict[str, TicketResult] = field(default_factory=dict)

    def create_ticket(self, command: TicketCommand) -> TicketResult:
        ticket_id = f"TICKET-{len(self.tickets) + 1:04d}"
        result = TicketResult(
            ticket_id=ticket_id,
            title=command.title,
            customer_id=command.customer_id,
            created=True,
        )
        self.tickets[ticket_id] = result
        return result


class LostResponse(RuntimeError):
    """The caller does not know whether the write succeeded."""


def run_idempotent_write(
    command: TicketCommand,
    *,
    idempotency_store: dict[str, TicketResult],
    write: Callable[[TicketCommand], TicketResult],
) -> TicketResult:
    """Return the original result when a retry repeats the same operation ID."""
    if command.operation_id in idempotency_store:
        existing = idempotency_store[command.operation_id]
        return TicketResult(
            ticket_id=existing.ticket_id,
            title=existing.title,
            customer_id=existing.customer_id,
            created=False,
        )

    result = write(command)
    idempotency_store[command.operation_id] = result
    return result


def unreliable_agent_attempt(
    command: TicketCommand,
    *,
    idempotency_store: dict[str, TicketResult],
    write: Callable[[TicketCommand], TicketResult],
    lose_response: bool,
) -> TicketResult:
    """Simulate a network timeout after the durable result has been recorded."""
    result = run_idempotent_write(
        command,
        idempotency_store=idempotency_store,
        write=write,
    )
    if lose_response:
        raise LostResponse("caller timed out before receiving the ticket id")
    return result


def main() -> None:
    system = FakeTicketSystem()
    store: dict[str, TicketResult] = {}

    command = TicketCommand(
        operation_id="support-import-2026-07-04-customer-42",
        title="Import failed for customer 42",
        customer_id="customer-42",
    )

    print("1) first attempt writes, records, then the caller loses the response:")
    try:
        unreliable_agent_attempt(
            command,
            idempotency_store=store,
            write=system.create_ticket,
            lose_response=True,
        )
    except LostResponse as exc:
        print(f"   timeout: {exc}")

    print("2) retry reuses the same operation ID and does not create a duplicate:")
    result = unreliable_agent_attempt(
        command,
        idempotency_store=store,
        write=system.create_ticket,
        lose_response=False,
    )

    print(f"   returned {result.ticket_id}, created={result.created}")
    print(f"   tickets in external system: {len(system.tickets)}")


if __name__ == "__main__":
    main()
