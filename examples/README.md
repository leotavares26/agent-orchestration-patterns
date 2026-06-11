# Worked examples

Runnable companions to the patterns in the [top-level README](../README.md). Each
one is dependency-free standard-library Python so you can read it, run it, and lift
the bits you need — no SDK, no API key, no network.

| Example | Pattern | What it shows |
|---|---|---|
| [`retry_with_backoff.py`](retry_with_backoff.py) | #10 Retry & error recovery | Classifying transient vs. malformed vs. permanent failures, exponential backoff with jitter, and a budget that stops runaway retries. |
| [`verifier_gate.py`](verifier_gate.py) | #11 Verifier gate | Separating a worker draft from the side effect until a concrete contract check passes. |

```bash
python examples/retry_with_backoff.py
python examples/verifier_gate.py
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
