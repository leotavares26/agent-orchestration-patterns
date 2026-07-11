"""
Worked example for Pattern #3 — Router / dispatcher.

One mega-prompt that tries to answer billing questions, debug code, and search
the docs all at once gets brittle and expensive. A router keeps the entry point
cheap: classify the request first, then hand it to a specialist that owns the
right prompt and tools.

This tiny example routes a support request to one of three handlers. The
"classifier" is a boring keyword scorer standing in for a small model call — the
point is the control flow, not the classification itself:

    - score the request against each route's signals
    - pick the best route, or fall back when nothing scores
    - dispatch to exactly one specialist handler

No LLM SDK, no network, no API key. Swap `classify` for a cheap model call and
the specialists for real chains, and the shape stays the same.

    python examples/router_dispatcher.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Route:
    """A specialist the router can dispatch to."""

    name: str
    # Words that hint a request belongs here. In production this is whatever the
    # classifier keys on — few-shot labels, embeddings, an intent enum.
    signals: tuple[str, ...]
    handle: Callable[[str], str]


def handle_billing(request: str) -> str:
    return "billing specialist: pulled the invoice and checked the plan tier"


def handle_code(request: str) -> str:
    return "code specialist: reproduced the error and proposed a patch"


def handle_search(request: str) -> str:
    return "docs specialist: retrieved the three most relevant pages"


def handle_fallback(request: str) -> str:
    return "general assistant: no specialist matched, answering directly"


ROUTES: tuple[Route, ...] = (
    Route("billing", ("invoice", "charge", "refund", "payment", "plan"), handle_billing),
    Route("code", ("error", "exception", "stack trace", "bug", "traceback"), handle_code),
    Route("search", ("docs", "how do i", "where is", "documentation"), handle_search),
)


def classify(request: str, routes: tuple[Route, ...] = ROUTES) -> tuple[Route | None, int]:
    """Score the request against each route and return the best match.

    Stands in for a lightweight model classifier. Returns (route, score); a
    score of 0 means nothing matched and the caller should fall back.
    """
    lowered = request.lower()
    best: Route | None = None
    best_score = 0
    for route in routes:
        score = sum(1 for signal in route.signals if signal in lowered)
        if score > best_score:
            best, best_score = route, score
    return best, best_score


def route_request(request: str) -> str:
    """Classify once, then dispatch to exactly one handler."""
    route, score = classify(request)
    if route is None or score == 0:
        return handle_fallback(request)
    return route.handle(request)


def main() -> None:
    requests = [
        "My invoice looks wrong and I want a refund on last month's charge.",
        "The worker crashes with a KeyError — here's the stack trace.",
        "How do I rotate an API key? Point me at the docs.",
        "Just saying hello, no real question here.",
    ]

    for request in requests:
        route, score = classify(request)
        label = route.name if route and score else "fallback"
        print(f"[{label:>8}] {request}")
        print(f"           -> {route_request(request)}\n")


if __name__ == "__main__":
    main()
