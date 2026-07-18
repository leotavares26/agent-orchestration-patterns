"""
Worked example for Pattern #8 — Memory-augmented agent.

A context window is finite, so a long-running agent can't just keep appending
turns forever — the oldest ones fall out and are forgotten. The fix is to stop
treating the prompt as the memory. Externalize state into three tiers:

    Short-term scratchpad -> the last few turns, kept verbatim in context
    Long-term store        -> durable facts written out as they're learned
    Retrieval              -> pull only the relevant slice back in per query

The discipline is that the model's context at any turn is *assembled*, not
accumulated: a bounded window of recent turns plus the handful of stored facts
that actually match the current question. Everything else lives outside the
window and is recalled on demand, so the agent stays coherent across a session
far longer than the raw context would allow — and across sessions, if the store
is persisted.

To stay self-contained there is no LLM SDK, no vector database, no network, and
no API key. Retrieval is keyword overlap instead of embeddings, and the "agent"
is a plain function. Swap the store for a real database and the overlap score
for a vector search and the shape is unchanged: write salient facts out, then
retrieve the matching slice before you answer.

    python examples/memory_augmented.py
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class Turn:
    """One exchange kept verbatim in the short-term scratchpad."""

    user: str
    agent: str


@dataclass
class Fact:
    """A durable memory written to the long-term store, tagged for retrieval."""

    text: str
    tags: set[str] = field(default_factory=set)


# --- Stop words so retrieval matches on content, not filler ------------------
STOP = {
    "a", "an", "and", "are", "do", "for", "i", "is", "it", "me", "my", "of",
    "on", "the", "to", "we", "what", "when", "where", "you", "your",
}


def keywords(text: str) -> set[str]:
    """Content words used both to tag stored facts and to score retrieval."""
    return {w.strip("?.,!").lower() for w in text.split()} - STOP - {""}


class MemoryAugmentedAgent:
    """Assembles context per turn instead of letting it grow unbounded.

    - Short-term: a fixed-size window of recent turns (older ones drop off).
    - Long-term: an append-only list of facts that survives past the window.
    - Retrieval: rank stored facts by keyword overlap with the current query
      and pull back only the top few.
    """

    def __init__(self, window: int = 2, top_k: int = 2) -> None:
        self.scratchpad: deque[Turn] = deque(maxlen=window)  # bounded context
        self.store: list[Fact] = []                          # durable memory
        self.top_k = top_k

    def remember(self, text: str) -> None:
        """Write a salient fact to the long-term store, tagged for recall."""
        self.store.append(Fact(text, keywords(text)))

    def recall(self, query: str) -> list[Fact]:
        """Retrieve the stored facts whose tags overlap the query most."""
        q = keywords(query)
        scored = [(len(q & f.tags), f) for f in self.store]
        hits = sorted((s for s in scored if s[0] > 0), key=lambda s: -s[0])
        return [f for _, f in hits[: self.top_k]]

    def _assemble_context(self, query: str) -> tuple[list[Turn], list[Fact]]:
        """The prompt is built fresh each turn: recent window + recalled slice."""
        return list(self.scratchpad), self.recall(query)

    def ask(self, query: str) -> str:
        recent, recalled = self._assemble_context(query)
        print(f"You: {query}")
        print(
            f"  [context: {len(recent)} recent turn(s), "
            f"{len(recalled)} fact(s) recalled from {len(self.store)} stored]"
        )

        # A real agent would send `recent` + `recalled` to the model. Here a
        # tiny stand-in answers from the recalled facts so you can see recall
        # working even after the original turn has left the short-term window.
        if recalled:
            answer = " ".join(f.text for f in recalled)
        elif recent:
            answer = "I only have our recent exchanges; nothing stored matches."
        else:
            answer = "I don't have anything on that yet."

        print(f"Agent: {answer}\n")
        self.scratchpad.append(Turn(query, answer))
        return answer


def main() -> None:
    agent = MemoryAugmentedAgent(window=2, top_k=2)

    # Early turns teach the agent durable facts. Each is written to the
    # long-term store *and* stays briefly in the short-term window.
    agent.remember("Deploys go out on Tuesdays after the 10am review.")
    agent.ask("Remember: deploys go out on Tuesdays after the 10am review.")

    agent.remember("The staging database is reset every night at 2am UTC.")
    agent.ask("Also note the staging database resets nightly at 2am UTC.")

    # Filler turns push the earliest exchange out of the 2-turn window.
    agent.ask("Thanks!")
    agent.ask("How's it going?")

    # The deploy turn is long gone from the scratchpad, but the fact was
    # externalized — so retrieval pulls it back in on a matching question.
    agent.ask("When do deploys happen?")
    agent.ask("What time does staging reset?")


if __name__ == "__main__":
    main()
