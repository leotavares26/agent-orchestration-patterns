"""
Worked example for Pattern #10 — Retry & error recovery.

The whole point of the pattern is that *not every failure is the same*. An agent
that retries blindly hammers a struggling service; one that gives up on the first
timeout drops tasks that would have worked on the second try. So we classify the
error first, then react:

    transient  (timeout, 429, 503)        -> retry with exponential backoff
    malformed  (bad JSON, schema error)   -> hand the error back to the caller to fix
    permanent  (auth, 404, bad input)     -> stop, escalate

The whole thing runs under a budget (max attempts + max wall-clock) so recovery
can never run away.

This file is dependency-free and self-contained: it simulates a flaky tool with a
deterministic seed so you can actually run it and watch the backoff happen.

    python examples/retry_with_backoff.py

No API keys, no network. See the README for how this maps onto a real LLM tool call.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass


# --- Error taxonomy -------------------------------------------------------- #
# In a real system these would wrap your HTTP client / SDK exceptions. The
# classification is the load-bearing part, not the class hierarchy.

class ToolError(Exception):
    """Base class for anything a tool call can raise."""


class TransientError(ToolError):
    """Worth retrying: timeouts, 429s, 503s, connection resets."""


class MalformedError(ToolError):
    """The call returned, but the payload was unusable (bad JSON, schema miss)."""


class PermanentError(ToolError):
    """Retrying will never help: auth failure, 404, invalid arguments."""


@dataclass
class RetryBudget:
    """A hard ceiling so recovery can't loop forever."""

    max_attempts: int = 5
    max_seconds: float = 30.0
    base_delay: float = 0.5      # first backoff, in seconds
    max_delay: float = 8.0       # cap so we don't sleep for minutes
    jitter: float = 0.1          # +/- fraction, to avoid thundering herds


def _backoff_delay(attempt: int, budget: RetryBudget) -> float:
    """Exponential backoff with full jitter, capped at max_delay."""
    raw = min(budget.base_delay * (2 ** attempt), budget.max_delay)
    spread = raw * budget.jitter
    return max(0.0, raw + random.uniform(-spread, spread))


def call_with_recovery(tool, *, budget: RetryBudget | None = None, sleep=time.sleep):
    """
    Run `tool()` under a retry budget, reacting to the *kind* of failure.

    Returns the tool's result, or re-raises once the budget is spent / the error
    is permanent. `sleep` is injectable so tests don't actually wait.
    """
    budget = budget or RetryBudget()
    started = time.monotonic()
    last_error: ToolError | None = None

    for attempt in range(budget.max_attempts):
        if time.monotonic() - started > budget.max_seconds:
            raise TimeoutError("retry budget (wall-clock) exhausted") from last_error

        try:
            return tool()

        except PermanentError:
            # No amount of retrying fixes auth/404/bad-input. Fail fast.
            raise

        except MalformedError as err:
            # The model/tool produced something unusable. In a real agent you'd
            # feed `err` back into the prompt so the model can self-correct its
            # next call. Here we just surface it after the budget is spent.
            last_error = err
            delay = _backoff_delay(attempt, budget)
            print(f"  attempt {attempt + 1}: malformed ({err}); self-correct + retry in {delay:.2f}s")
            sleep(delay)

        except TransientError as err:
            last_error = err
            delay = _backoff_delay(attempt, budget)
            print(f"  attempt {attempt + 1}: transient ({err}); backoff {delay:.2f}s")
            sleep(delay)

    raise TimeoutError(f"retry budget (attempts) exhausted after {budget.max_attempts}") from last_error


# --- Demo ------------------------------------------------------------------ #

def flaky_tool(fail_times: int):
    """A stand-in for a real tool call that fails `fail_times` before succeeding."""
    state = {"calls": 0}

    def _call():
        state["calls"] += 1
        if state["calls"] <= fail_times:
            raise TransientError(f"503 service unavailable (call #{state['calls']})")
        return {"ok": True, "calls": state["calls"]}

    return _call


def main() -> None:
    random.seed(7)  # deterministic output for the demo

    print("1) recovers after a couple of transient failures:")
    result = call_with_recovery(flaky_tool(fail_times=2))
    print(f"  -> success: {result}\n")

    print("2) permanent error fails fast, no retries:")
    def bad_auth():
        raise PermanentError("401 unauthorized")
    try:
        call_with_recovery(bad_auth)
    except PermanentError as err:
        print(f"  -> stopped immediately and escalated: {err}\n")

    print("3) budget caps runaway retries:")
    try:
        call_with_recovery(flaky_tool(fail_times=99), budget=RetryBudget(max_attempts=3))
    except TimeoutError as err:
        print(f"  -> gave up cleanly: {err}")


if __name__ == "__main__":
    main()
