"""
Worked example for Pattern #5 — Supervisor (multi-agent).

When one agent tries to be researcher, coder, and editor at once, its context
bloats and its instructions start contradicting each other. The supervisor
pattern splits the work: a coordinator owns the *goal* and delegates each
separable sub-task to a specialist that owns a *narrow* job with its own focused
context and tools. The supervisor never does the specialist work itself — it
routes, collects results, and integrates.

    Supervisor         -> decomposes goal, assigns each sub-task to a specialist
    Specialist agents  -> each handles one job with its own focused context
    Supervisor         -> integrates the returned results into one answer

The key discipline is the handoff contract. Each delegation carries an explicit
sub-goal and each specialist returns a small structured result (not a blob), so
the supervisor can integrate deterministically and spot a specialist that failed
or went out of scope. That structure is what keeps multi-agent from turning into
a game of telephone.

To stay self-contained there is no LLM SDK, no network, and no API key. Each
"agent" is a plain function that stands in for a model call with a focused
prompt and tools. Swap any specialist for a real agent that accepts a sub-goal
and returns the same Result shape and the coordination is unchanged.

    python examples/supervisor.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Result:
    """The handoff contract every specialist returns to the supervisor.

    Keeping this small and structured (not a free-text blob) is what lets the
    supervisor integrate results deterministically and detect a specialist that
    errored or drifted out of its lane.
    """

    specialist: str
    ok: bool
    summary: str
    payload: dict = field(default_factory=dict)


# --- Specialist agents ------------------------------------------------------
# Each owns one narrow job. A real implementation would prompt a model with a
# focused system prompt and a small tool set; the signature stays the same:
# take a sub-goal string, return a Result.

def researcher(subgoal: str) -> Result:
    facts = {
        "market size": "The global widget market is ~$4.2B, growing 7% YoY.",
        "top competitor": "Acme Widgets leads with ~30% share.",
    }
    hit = next((v for k, v in facts.items() if k in subgoal.lower()), None)
    if hit is None:
        return Result("researcher", False, f"No source found for {subgoal!r}.")
    return Result("researcher", True, hit, {"citation": "internal-brief-2024"})


def analyst(subgoal: str, *, context: dict) -> Result:
    # Specialists can read what earlier specialists produced, passed in
    # explicitly by the supervisor — never by sharing one giant scratchpad.
    if "growth" not in context:
        return Result("analyst", False, "Missing growth input from research.")
    verdict = "attractive" if context["growth"] >= 5 else "flat"
    return Result(
        "analyst",
        True,
        f"At {context['growth']}% YoY the segment looks {verdict}.",
        {"verdict": verdict},
    )


def writer(subgoal: str, *, context: dict) -> Result:
    verdict = context.get("verdict", "unknown")
    line = f"Recommendation: the market is {verdict}; proceed to a scoped pilot."
    return Result("writer", True, line, {"deliverable": line})


# --- Supervisor -------------------------------------------------------------
# Owns the goal. Decides who does what, hands each specialist an explicit
# sub-goal plus only the context it needs, and integrates the results. It does
# no specialist work itself.

@dataclass
class Delegation:
    specialist: str
    subgoal: str
    run: Callable[[], Result]


class Supervisor:
    def __init__(self) -> None:
        self.results: list[Result] = []

    def _record(self, result: Result) -> Result:
        status = "ok" if result.ok else "FAILED"
        print(f"  <- {result.specialist} [{status}]: {result.summary}")
        self.results.append(result)
        return result

    def run(self, goal: str) -> str:
        print(f"Goal: {goal}\n")

        # Step 1: research (two independent lookups the researcher owns).
        print("Supervisor -> researcher (gather market facts)")
        size = self._record(researcher("market size"))
        comp = self._record(researcher("top competitor"))
        if not (size.ok and comp.ok):
            return "Halted: research incomplete, escalating to a human."

        # Step 2: analysis — supervisor passes forward only what's needed.
        print("\nSupervisor -> analyst (assess attractiveness)")
        analysis = self._record(analyst("assess growth", context={"growth": 7}))
        if not analysis.ok:
            return "Halted: analysis failed, escalating to a human."

        # Step 3: write-up, seeded with the analyst's verdict.
        print("\nSupervisor -> writer (draft recommendation)")
        draft = self._record(
            writer("draft memo", context={"verdict": analysis.payload["verdict"]})
        )

        # Integrate: the supervisor composes the final answer from the pieces.
        print("\nSupervisor integrates results:")
        answer = "\n".join(
            [
                f"- Market: {size.summary}",
                f"- Competition: {comp.summary}",
                f"- Analysis: {analysis.summary}",
                f"- {draft.payload['deliverable']}",
            ]
        )
        print(answer)
        return answer


def main() -> None:
    Supervisor().run("Should we enter the widget market?")


if __name__ == "__main__":
    main()
