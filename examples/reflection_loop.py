"""
Worked example for Pattern #4 — Reflection / self-critique.

Reflection turns a single guess into a short improvement loop:

    generate -> critique against criteria -> revise -> (repeat, bounded)

The value is in the *criteria* and the *bound*. A critique with no concrete
rubric just produces another confident opinion, and a loop with no cap can
revise forever. So the critic here returns specific, actionable issues, and the
loop stops the moment the draft is clean or the attempt budget runs out.

To stay self-contained there is no LLM SDK, no network, and no API key: the
"generator" and "reviser" are deterministic stand-ins. The point is the control
flow, not the text quality — swap the stubs for real model calls and the loop is
unchanged.

    python examples/reflection_loop.py
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Critique:
    """The critic's verdict for one pass. `ok` is True only when nothing is left."""

    ok: bool
    issues: list[str] = field(default_factory=list)


def critique_summary(draft: str, *, max_chars: int = 120) -> Critique:
    """An explicit rubric beats a vague 'make it better'.

    Each check maps to a concrete, fixable issue so the reviser knows exactly
    what to change on the next pass.
    """
    issues: list[str] = []
    text = draft.strip()

    if not text:
        issues.append("summary is empty")
    if len(text) > max_chars:
        issues.append(f"too long ({len(text)} > {max_chars} chars)")
    if "TODO" in text:
        issues.append("contains a placeholder ('TODO')")
    if not text.endswith("."):
        issues.append("should end with a period")
    for weasel in ("very", "really", "stuff", "things"):
        if weasel in text.lower().split():
            issues.append(f"vague word: {weasel!r}")

    return Critique(ok=not issues, issues=issues)


def revise(draft: str, critique: Critique, *, max_chars: int = 120) -> str:
    """Apply the critic's issues. A real agent would feed the issues back to the
    model; here we fix them deterministically so the example runs anywhere."""
    text = draft.strip()

    if "contains a placeholder ('TODO')" in critique.issues:
        text = text.replace("TODO", "the retry budget").strip()
    for weasel in ("very", "really", "stuff", "things"):
        text = " ".join(w for w in text.split() if w.lower() != weasel)
    if not text.endswith("."):
        text = text.rstrip(".") + "."
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "."

    return text


def reflect(draft: str, *, max_passes: int = 3) -> str:
    """Generate is done; now critique -> revise under a hard pass budget."""
    for attempt in range(1, max_passes + 1):
        critique = critique_summary(draft)
        if critique.ok:
            print(f"  pass {attempt}: clean — stopping early")
            return draft

        print(f"  pass {attempt}: {len(critique.issues)} issue(s): {', '.join(critique.issues)}")
        draft = revise(draft, critique)

    # Budget exhausted. Return the best draft and let the caller decide whether
    # to ship it, escalate, or hand it to a stronger verifier.
    print(f"  budget of {max_passes} passes exhausted — returning best effort")
    return draft


def main() -> None:
    rough_draft = "This adds TODO retry logic and cleans up some really messy stuff"
    print("initial draft:")
    print(f"  {rough_draft!r}\n")

    final = reflect(rough_draft)

    print("\nfinal draft:")
    print(f"  {final!r}")
    print(f"  clean: {critique_summary(final).ok}")


if __name__ == "__main__":
    main()
