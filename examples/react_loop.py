"""
Worked example for Pattern #1 — ReAct loop.

The foundational agent shape: instead of answering in one shot, the model
interleaves reasoning with tool use, one step at a time:

    Thought      -> what do I need next?
    Action       -> call a tool with an argument
    Observation  -> read the result, then think again

The loop repeats until the model decides it has enough to answer, or a step
budget stops it. The key property is that each decision is made *after* seeing
the previous observation, so the agent can react to what the world actually
returned instead of committing to a fixed plan up front (that's Pattern #2).

To stay self-contained there is no LLM SDK, no network, and no API key. The
"policy" that picks the next action is a deterministic stand-in for a model:
it reads the running scratchpad and returns the next Thought/Action. Swap it
for a real model call that emits the same structure and the control flow is
unchanged.

    python examples/react_loop.py
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Turn:
    """One Thought -> Action -> Observation step, recorded on the scratchpad."""

    thought: str
    action: str = ""
    arg: str = ""
    observation: str = ""


@dataclass
class Scratchpad:
    """The agent's running memory of the loop so far.

    A real ReAct prompt serializes this back into the context every turn, so the
    model always reasons over everything it has seen. Keeping it explicit (rather
    than buried in a prompt string) makes the loop easy to inspect and replay.
    """

    goal: str
    turns: list[Turn] = field(default_factory=list)

    def transcript(self) -> str:
        lines = [f"Question: {self.goal}"]
        for t in self.turns:
            lines.append(f"Thought: {t.thought}")
            if t.action:
                lines.append(f"Action: {t.action}[{t.arg}]")
                lines.append(f"Observation: {t.observation}")
        return "\n".join(lines)


# --- Fake tools -------------------------------------------------------------
# Each returns a short observation string. A real agent would swap these for
# search, code execution, HTTP calls, etc. The signatures stay the same.

def lookup(entity: str) -> str:
    facts = {
        "eiffel tower": "The Eiffel Tower is 330 metres tall.",
        "statue of liberty": "The Statue of Liberty is 93 metres tall.",
    }
    return facts.get(entity.lower(), f"No entry for {entity!r}.")


def calc(expression: str) -> str:
    # Deterministic and sandboxed: only arithmetic on digits/operators.
    allowed = set("0123456789+-*/(). ")
    if not expression or set(expression) - allowed:
        return "ERROR: unsupported expression"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))  # noqa: S307
    except ArithmeticError:
        return "ERROR: bad arithmetic"


TOOLS = {"lookup": lookup, "calc": calc}


# --- Policy (stand-in for the model) ---------------------------------------
# Reads the scratchpad and decides the next Thought + Action. A real
# implementation prompts a model with the transcript and parses its reply into
# the same (thought, action, arg) shape. Returning action="" means "answer now".

def policy(pad: Scratchpad) -> Turn:
    lookups = [t for t in pad.turns if t.action == "lookup"]
    did_calc = any(t.action == "calc" for t in pad.turns)

    if len(lookups) == 0:
        return Turn(
            thought="I need each tower's height before I can compare them.",
            action="lookup",
            arg="Eiffel Tower",
        )
    if len(lookups) == 1:
        return Turn(
            thought="Got the Eiffel Tower. Now the Statue of Liberty.",
            action="lookup",
            arg="Statue of Liberty",
        )
    if not did_calc:
        return Turn(
            thought="I have both heights (330 and 93). Compute the difference.",
            action="calc",
            arg="330 - 93",
        )
    # Enough observations gathered — emit the final answer, no further action.
    return Turn(thought="The difference is on the scratchpad; I can answer now.")


def run(goal: str, *, max_steps: int = 6) -> str:
    """Drive the Thought -> Action -> Observation loop under a step budget."""
    pad = Scratchpad(goal=goal)
    print(f"Question: {goal}\n")

    for _step in range(1, max_steps + 1):
        turn = policy(pad)
        print(f"Thought: {turn.thought}")

        if not turn.action:  # the model chose to answer
            pad.turns.append(turn)
            last_calc = next(
                (t.observation for t in reversed(pad.turns) if t.action == "calc"),
                "unknown",
            )
            answer = (
                f"The Eiffel Tower is {last_calc} metres taller than the "
                "Statue of Liberty."
            )
            print(f"Answer: {answer}")
            return answer

        if turn.action not in TOOLS:
            turn.observation = f"ERROR: no tool named {turn.action!r}"
        else:
            turn.observation = TOOLS[turn.action](turn.arg)
        print(f"Action: {turn.action}[{turn.arg}]")
        print(f"Observation: {turn.observation}\n")
        pad.turns.append(turn)

    # Budget exhausted without an answer — stop instead of looping forever.
    print("Step budget exhausted — stopping without a final answer.")
    return "(no answer: budget exhausted)"


def main() -> None:
    run("How much taller is the Eiffel Tower than the Statue of Liberty?")


if __name__ == "__main__":
    main()
