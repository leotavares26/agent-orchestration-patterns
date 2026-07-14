"""
Worked example for Pattern #2 — Plan-and-execute.

A pure ReAct loop decides the next step from scratch every turn, which drifts on
long tasks. Plan-and-execute splits the work in two:

    planner  -> draft an explicit, ordered plan
    executor -> run one step at a time
    replanner-> when a step's result disagrees with the plan, revise the rest

The value is the *visible plan* and the *replan trigger*. The plan is auditable
before anything runs, and the executor doesn't silently improvise — a surprising
observation forces an explicit revision instead of quiet drift.

To stay self-contained there is no LLM SDK, no network, and no API key. The
planner, the fake tools, and the replanner are deterministic stand-ins; swap
them for real model/tool calls and the control flow is unchanged.

    python examples/plan_and_execute.py
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    """One planned action. `done` and `result` are filled in as it executes."""

    action: str
    arg: str
    done: bool = False
    result: str = ""


@dataclass
class Plan:
    goal: str
    steps: list[Step] = field(default_factory=list)

    def next_pending(self) -> Step | None:
        return next((s for s in self.steps if not s.done), None)


# --- Fake tools -------------------------------------------------------------
# Each returns a short observation string. One of them "discovers" a fact that
# the original plan didn't account for, which is what triggers a replan.

def search(query: str) -> str:
    return f"3 results for {query!r}"


def fetch(url: str) -> str:
    # The surprise: the source turns out to be paywalled, so the drafted
    # "summarize" step can't run against it as planned.
    if "annual-report" in url:
        return "PAYWALL: full text unavailable"
    return f"200 OK, 1.2kb from {url}"


def summarize(text: str) -> str:
    return f"summary of {text[:24]!r}"


TOOLS = {"search": search, "fetch": fetch, "summarize": summarize}


def plan(goal: str) -> Plan:
    """Draft the whole plan up front so it can be inspected before running.

    A real planner would prompt a model for ordered steps; here the plan is
    fixed so the example is deterministic.
    """
    return Plan(
        goal=goal,
        steps=[
            Step("search", "competitor revenue 2025"),
            Step("fetch", "https://example.com/annual-report.pdf"),
            Step("summarize", "annual report"),
        ],
    )


def replan(current: Plan, failed: Step) -> Plan:
    """Reality disagreed with the plan. Revise only the remaining steps instead
    of starting over — the completed work still stands.
    """
    kept = [s for s in current.steps if s.done]
    if failed.action == "fetch" and "PAYWALL" in failed.result:
        # Route around the paywall: find an open summary instead of fetching it.
        kept += [
            Step("search", "annual report press-release summary"),
            Step("summarize", "press release"),
        ]
    else:
        # No known recovery — re-queue the step once and let the budget catch a loop.
        kept.append(Step(failed.action, failed.arg))
    return Plan(goal=current.goal, steps=kept)


def execute(goal: str, *, max_replans: int = 2) -> Plan:
    """Run the plan step by step, replanning on surprises under a hard budget."""
    current = plan(goal)
    print(f"goal: {goal}")
    print("initial plan: " + " -> ".join(f"{s.action}({s.arg})" for s in current.steps))

    replans = 0
    while (step := current.next_pending()) is not None:
        step.result = TOOLS[step.action](step.arg)
        surprised = step.result.startswith("PAYWALL")
        print(f"  run {step.action}({step.arg!r}) -> {step.result}")

        if surprised:
            if replans >= max_replans:
                print("  replan budget exhausted — escalating")
                break
            replans += 1
            current = replan(current, step)
            print(f"  replan #{replans}: " + " -> ".join(
                f"{s.action}({s.arg})" for s in current.steps if not s.done))
            continue

        step.done = True

    return current


def main() -> None:
    final = execute("Estimate a competitor's 2025 revenue")
    completed = [s for s in final.steps if s.done]
    print(f"\ndone: {len(completed)}/{len(final.steps)} steps completed")
    print("final result: " + (completed[-1].result if completed else "(none)"))


if __name__ == "__main__":
    main()
