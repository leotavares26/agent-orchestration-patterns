# Agent Orchestration Patterns

A practical reference of design patterns for building LLM agents that hold up outside of a demo.

Most "agent" tutorials stop at a single ReAct loop. Real systems need structure: how do you plan, route, recover from errors, keep humans in the loop, and coordinate more than one agent without it turning into spaghetti? These are the patterns I keep coming back to, with notes on *when* each one earns its complexity.

> Maintained by [Leo Tavares](https://github.com/leotavares26). More patterns and worked examples are added over time — see the [companion notes](https://github.com/leotavares26/building-agents-notes) and my [blog](https://scale-agents.hashnode.dev/).

## How to read this

Each pattern has the same shape:

- **Problem** — the failure mode it addresses
- **Shape** — the control flow in one breath
- **Use when / avoid when** — the honest tradeoffs

Start simple. Reach for a heavier pattern only when a lighter one demonstrably breaks.

---

## 1. ReAct loop

**Problem:** The model needs to act on the world (search, call APIs, run code), not just answer in one shot.

**Shape:** `Thought → Action → Observation`, repeated until the model decides it's done.

**Use when:** Tasks need tool use and the number of steps is unknown up front.
**Avoid when:** The task is a fixed pipeline — a hardcoded sequence is cheaper and more reliable than letting the model decide every step.

## 2. Plan-and-execute

**Problem:** Long tasks drift. A pure ReAct loop loses the plot over many steps.

**Shape:** A planner drafts an explicit multi-step plan; an executor runs each step; a replanner revises when reality disagrees.

**Use when:** Tasks are long-horizon and benefit from a visible, auditable plan.
**Avoid when:** Two or three tool calls would do — planning overhead isn't worth it.

## 3. Router / dispatcher

**Problem:** One mega-prompt trying to handle every request becomes brittle and expensive.

**Shape:** A lightweight classifier routes each request to a specialized sub-agent or chain.

**Use when:** You have distinct task types (billing vs. code vs. search) with different tools or prompts.
**Avoid when:** Requests are homogeneous — the extra hop just adds latency.

## 4. Reflection / self-critique

**Problem:** First drafts are often wrong in ways the model can catch itself.

**Shape:** Generate → critique against criteria → revise. Optionally loop a bounded number of times.

**Use when:** Output quality matters more than latency (code, analysis, writing).
**Avoid when:** You're latency-bound, or you have a real verifier (tests, types) that beats self-critique.

## 5. Supervisor (multi-agent)

**Problem:** A single agent juggling many roles gets confused and its context bloats.

**Shape:** A supervisor delegates to specialist agents and integrates their results.

**Use when:** Sub-tasks are genuinely separable and benefit from focused context.
**Avoid when:** A single agent with good tools works — multi-agent multiplies cost and failure modes.

## 6. Human-in-the-loop

**Problem:** Some actions are irreversible or high-stakes (sending money, deleting data, emailing customers).

**Shape:** The agent pauses at a checkpoint and waits for human approval before continuing.

**Use when:** Mistakes are expensive and trust is still being earned.
**Avoid when:** The action is cheap and reversible — friction with no payoff.

## 7. Tool-use guardrails

**Problem:** Free-form tool calls can be malformed, unsafe, or out of bounds.

**Shape:** Validate arguments (schemas/types), constrain which tools are available per state, and sandbox side effects.

**Use when:** Always, for anything touching production systems.

## 8. Memory-augmented agent

**Problem:** Context windows are finite; agents forget what happened earlier or across sessions.

**Shape:** Externalize state — short-term scratchpad, long-term store, and retrieval to pull the right slice back in.

**Use when:** Tasks span long sessions or need continuity across runs.
**Avoid when:** Everything fits comfortably in context — don't add a database you don't need.

## 9. Parallel fan-out / gather

**Problem:** A task splits into independent sub-tasks, and running them one after another wastes wall-clock time — the agent sits idle waiting on each call before starting the next.

**Shape:** Scatter the sub-tasks to run concurrently, then gather and merge the results. A coordinator decides the split, fires the workers in parallel, and reconciles their outputs (dedupe, rank, or synthesize).

**Use when:** Sub-tasks are genuinely independent and latency matters — fan-out research across several sources, summarize many documents, or probe a question from multiple angles at once.
**Avoid when:** Sub-tasks depend on each other's output (you need a pipeline, not a fan-out), or the merge step is harder than the work itself. Watch the cost too — N parallel calls is N times the spend, and rate limits bite faster.

> Distinct from the **Supervisor** pattern: supervision is about *who owns which role*; fan-out is about *doing separable work at the same time*. They compose well — a supervisor that dispatches in parallel instead of in sequence.

## 10. Retry & error recovery

**Problem:** Tool calls fail for boring reasons — a timeout, a rate limit, a transient 5xx, a malformed response. An agent that treats every failure as final gives up on tasks that would have succeeded on the second try; one that retries blindly hammers a struggling service and loops forever.

**Shape:** Classify the error before reacting. *Transient* (timeouts, 429s, 503s) → retry with exponential backoff and a capped attempt count. *Malformed* (bad JSON, schema violation) → feed the error back to the model and let it self-correct the next call. *Permanent* (auth failure, 404, invalid input) → stop retrying and escalate. Wrap the whole thing in a budget (max attempts, max wall-clock) so recovery can't run away.

**Use when:** Anything that talks to a network or an external system — which is most real agents.
**Avoid when:** Nothing, really — but don't retry non-idempotent actions (a charge, an email send) without a dedupe key, or you'll do the thing twice.

> Pairs with **Human-in-the-loop**: when the retry budget is exhausted on a high-stakes action, escalate to a person instead of failing silently or trying forever.

## 11. Verifier gate

**Problem:** Models are good at producing plausible answers, but production systems need a sharper question: did this output actually satisfy the contract?

**Shape:** Let the agent draft the answer or action, then run an independent verifier before side effects happen. The verifier can be deterministic (tests, schema validation, policy checks), model-based with a stricter rubric, or both. Only verified outputs move forward; failures route back for repair or escalation.

**Use when:** There is a clear contract to check — generated code, structured extraction, SQL, policy-sensitive messages, or any workflow with irreversible side effects.
**Avoid when:** There is no reliable success criterion yet. A vague verifier just adds another confident model opinion; write the contract first.

> Keep the verifier smaller than the worker. The best version is often boring: unit tests, JSON Schema, type checks, allowlists, and a short failure message the agent can act on.


## 12. Budgeted loop / runtime brakes

**Problem:** Long-running agents fail by quietly doing "one more step" forever — polling, retrying, browsing, or spending tokens without a clear stop condition.

**Shape:** Put every loop under explicit budgets: max iterations, wall-clock time, spend/tool-call caps, and escalation thresholds. Persist the budget state so a restart does not reset the counter. Each pass does a cheap progress check and chooses one of three outcomes: continue, checkpoint, or stop/escalate.

**Use when:** Agents run unattended, watch queues, process batches, or operate on tasks where success may take many small steps.
**Avoid when:** The work is a fixed one-shot pipeline. Even then, keep a timeout — it is still a budget, just a boring one.

> Pairs with **Retry & error recovery** and **Memory-augmented agent**: retries need a budget, and durable state keeps runtime brakes from disappearing after a crash.

---

## Worked examples

The patterns above are deliberately prose-first — the tradeoffs matter more than any one implementation. Where a pattern benefits from seeing the control flow in code, there's a runnable, dependency-free example under [`examples/`](examples/):

- [`retry_with_backoff.py`](examples/retry_with_backoff.py) — Pattern #10, error classification + exponential backoff under a budget. Run it with `python examples/retry_with_backoff.py`.
- [`verifier_gate.py`](examples/verifier_gate.py) — Pattern #11, separating a worker draft from the side effect until a contract check passes. Run it with `python examples/verifier_gate.py`.

More examples get added alongside the patterns over time.

---

## A rule of thumb

> Complexity should be *earned*. Every extra agent, loop, or store is another thing that can fail at 2am. Ship the simplest shape that works, measure where it breaks, and add structure exactly there.

## Contributing

Have a pattern you rely on, or a sharper take on the tradeoffs? Open an issue or PR.

## License

[MIT](LICENSE)
