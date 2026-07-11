# Worked examples

Runnable companions to the patterns in the [top-level README](../README.md). Each
one is dependency-free standard-library Python so you can read it, run it, and lift
the bits you need — no SDK, no API key, no network.

| Example | Pattern | What it shows |
|---|---|---|
| [`router_dispatcher.py`](router_dispatcher.py) | #3 Router / dispatcher | Classifying a request against each route's signals, then dispatching to exactly one specialist handler with a fallback when nothing scores. |
| [`reflection_loop.py`](reflection_loop.py) | #4 Reflection / self-critique | Bounded generate -> critique -> revise loop driven by a concrete rubric, stopping as soon as the draft is clean. |
| [`tool_guardrails.py`](tool_guardrails.py) | #7 Tool-use guardrails | Checking state allowlists, required arguments, and human approval before a proposed tool call is dispatched. |
| [`fan_out_gather.py`](fan_out_gather.py) | #9 Parallel fan-out / gather | Running independent checks concurrently, then deduping and ranking findings before choosing the next step. |
| [`retry_with_backoff.py`](retry_with_backoff.py) | #10 Retry & error recovery | Classifying transient vs. malformed vs. permanent failures, exponential backoff with jitter, and a budget that stops runaway retries. |
| [`verifier_gate.py`](verifier_gate.py) | #11 Verifier gate | Separating a worker draft from the side effect until a concrete contract check passes. |
| [`budgeted_loop.py`](budgeted_loop.py) | #12 Budgeted loop / runtime brakes | Persisting loop counters so iteration, tool-call, and wall-clock budgets survive restarts. |
| [`state_machine_workflow.py`](state_machine_workflow.py) | #13 State machine / workflow graph | Making phases explicit with transition reasons and per-state tool permissions. |
| [`idempotent_side_effects.py`](idempotent_side_effects.py) | #14 Idempotent side effects | Using stable operation IDs so retries replay an existing write instead of duplicating it. |

```bash
python examples/router_dispatcher.py
python examples/reflection_loop.py
python examples/tool_guardrails.py
python examples/fan_out_gather.py
python examples/retry_with_backoff.py
python examples/verifier_gate.py
python examples/budgeted_loop.py
python examples/state_machine_workflow.py
python examples/idempotent_side_effects.py
```

## Mapping the demo onto a real tool call

The examples simulate a flaky tool so they stay self-contained. In a real agent,
swap the simulated failures for your client's exceptions and keep the
classification:

```python
try:
    return client.chat.completions.create(...)   # or any tool/HTTP call
except (httpx.TimeoutException, RateLimitError):
    raise TransientError(...)        # -> backoff and retry
except json.JSONDecodeError:
    raise MalformedError(...)        # -> feed the error back to the model
except AuthenticationError:
    raise PermanentError(...)        # -> stop, escalate
```

Read credentials from the environment — never hardcode them. Copy
[`.env.example`](../.env.example) to `.env`, fill it in, and load it with
`os.environ` / `python-dotenv`. The `.env` file stays out of git.
