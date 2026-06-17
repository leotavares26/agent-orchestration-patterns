"""
Worked example for Pattern #12 — Budgeted loop / runtime brakes.

Long-running agents tend to fail by doing "one more step" forever: another poll,
another retry, another browser action, another token spend. Runtime brakes make
that impossible by putting the loop under explicit budgets and persisting those
counters outside the prompt.

This demo processes a tiny queue under three budgets:

    - max loop iterations
    - max tool calls
    - max wall-clock seconds

The budget state is saved to disk after each pass. If the process restarts, it
loads the same counters instead of pretending the loop is fresh.

    python examples/budgeted_loop.py

No SDK, no network, no API keys. The fake "tool" is just a function call so the
control flow stays visible.
"""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class LoopBudget:
    """A persisted ceiling for an unattended loop."""

    max_iterations: int = 5
    max_tool_calls: int = 8
    max_seconds: float = 10.0
    iterations: int = 0
    tool_calls: int = 0
    started_at: float = 0.0

    @classmethod
    def load(cls, path: Path) -> "LoopBudget":
        if not path.exists():
            return cls(started_at=time.time())

        data = json.loads(path.read_text())
        return cls(**data)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")

    def spent(self) -> list[str]:
        """Return the reasons the loop must stop, if any."""
        reasons: list[str] = []
        elapsed = time.time() - self.started_at

        if self.iterations >= self.max_iterations:
            reasons.append(f"iteration budget spent ({self.iterations}/{self.max_iterations})")
        if self.tool_calls >= self.max_tool_calls:
            reasons.append(f"tool-call budget spent ({self.tool_calls}/{self.max_tool_calls})")
        if elapsed >= self.max_seconds:
            reasons.append(f"wall-clock budget spent ({elapsed:.2f}/{self.max_seconds:.2f}s)")

        return reasons


@dataclass
class QueueState:
    pending: list[str]
    completed: list[str]

    @property
    def done(self) -> bool:
        return not self.pending


def fake_tool(task: str) -> str:
    """Pretend this is a browser action, API call, or model invocation."""
    return f"processed {task}"


def cheap_progress_check(state: QueueState) -> str:
    """
    Decide whether to continue before doing expensive work.

    Real agents can make this deterministic: queue length changed, row count
    increased, tests are still failing, last checkpoint is older than N minutes.
    """
    if state.done:
        return "stop"
    if len(state.completed) and len(state.completed) % 3 == 0:
        return "checkpoint"
    return "continue"


def run_loop(state: QueueState, budget_path: Path) -> None:
    budget = LoopBudget.load(budget_path)

    while True:
        stop_reasons = budget.spent()
        if stop_reasons:
            print("ESCALATE: " + "; ".join(stop_reasons))
            print(f"Remaining work: {state.pending}\n")
            return

        decision = cheap_progress_check(state)
        if decision == "stop":
            print("DONE: queue is empty\n")
            return
        if decision == "checkpoint":
            print(f"CHECKPOINT: {len(state.completed)} done, {len(state.pending)} pending")
            # A real agent might persist a summary or ask for approval here. The
            # demo keeps going so you can see the next budgeted step.

        task = state.pending.pop(0)
        budget.iterations += 1
        budget.tool_calls += 1

        result = fake_tool(task)
        state.completed.append(result)
        budget.save(budget_path)

        print(f"iteration {budget.iterations}: {result}")


def main() -> None:
    tasks = ["inbox", "calendar", "docs", "sheet", "repo", "report"]

    with tempfile.TemporaryDirectory() as tmp:
        budget_path = Path(tmp) / "loop-budget.json"
        state = QueueState(pending=tasks.copy(), completed=[])

        print("1) first run stops at the iteration budget:")
        LoopBudget(max_iterations=3, max_tool_calls=10, max_seconds=30.0, started_at=time.time()).save(budget_path)
        run_loop(state, budget_path)

        print("2) restart loads the same counters, so the budget is still spent:")
        run_loop(state, budget_path)

        print("3) operator raises the budget and the remaining work completes:")
        saved = LoopBudget.load(budget_path)
        saved.max_iterations = 10
        saved.save(budget_path)
        run_loop(state, budget_path)


if __name__ == "__main__":
    main()
