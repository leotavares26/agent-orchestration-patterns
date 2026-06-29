"""
Worked example for Pattern #9 — Parallel fan-out / gather.

Some agent tasks split cleanly into independent probes: search three sources,
summarize several docs, or ask specialists for separate checks. Fan-out runs
those probes concurrently; gather merges the results into one decision.

This demo keeps everything local and deterministic. Each "worker" scores a
candidate plan from a different angle, then the coordinator dedupes and ranks the
findings before choosing the safest next step.

    python examples/fan_out_gather.py

No SDK, no network, no API keys. Swap `score_from_angle` for real tool calls when
the sub-tasks are genuinely independent.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    angle: str
    verdict: str
    risk: int  # 1 = low, 5 = high
    note: str


ANGLES = ("correctness", "latency", "operator-experience")


def score_from_angle(angle: str, plan: str) -> list[Finding]:
    """Pretend this is a specialist agent or external tool call."""
    lowered = plan.lower()

    if angle == "correctness":
        if "verify" in lowered or "test" in lowered:
            return [Finding(angle, "pass", 1, "plan includes an explicit verification step")]
        return [Finding(angle, "revise", 4, "add a verifier before side effects")]

    if angle == "latency":
        if "parallel" in lowered:
            return [Finding(angle, "watch", 3, "parallel work improves wall-clock but raises cost")]
        return [Finding(angle, "pass", 2, "sequential path is slower but simple")]

    if angle == "operator-experience":
        if "checkpoint" in lowered:
            return [Finding(angle, "pass", 1, "operator gets a clear pause point")]
        return [Finding(angle, "revise", 3, "add a human-readable checkpoint")]

    return [Finding(angle, "watch", 3, "unknown angle")]


def fan_out(plan: str, angles: Iterable[str]) -> list[Finding]:
    """Run independent checks concurrently and collect every finding."""
    findings: list[Finding] = []

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(score_from_angle, angle, plan) for angle in angles]
        for future in as_completed(futures):
            findings.extend(future.result())

    return findings


def gather(findings: list[Finding]) -> list[Finding]:
    """Dedupe and rank findings so the coordinator has one clean summary."""
    unique = {(f.angle, f.verdict, f.note): f for f in findings}
    return sorted(unique.values(), key=lambda f: (-f.risk, f.angle))


def choose_next_step(findings: list[Finding]) -> str:
    blockers = [f for f in findings if f.verdict == "revise" and f.risk >= 4]
    if blockers:
        return "revise before running: " + "; ".join(f.note for f in blockers)

    watches = [f.note for f in findings if f.verdict == "watch"]
    if watches:
        return "run with watchpoints: " + "; ".join(watches)

    return "run the plan"


def main() -> None:
    plan = "Run candidate fixes in parallel, then checkpoint with tests before shipping."

    raw_findings = fan_out(plan, ANGLES)
    ranked_findings = gather(raw_findings)

    print("FINDINGS:")
    for finding in ranked_findings:
        print(f"- [{finding.angle}] {finding.verdict} risk={finding.risk}: {finding.note}")

    print("\nNEXT STEP:")
    print(choose_next_step(ranked_findings))


if __name__ == "__main__":
    main()
