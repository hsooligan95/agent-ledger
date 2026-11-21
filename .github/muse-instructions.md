# Copilot instructions — agent-ledger

You are working in **AgentLedger**, FinOps for AI agents: OpenTelemetry
cost attribution for LangGraph agents (agent -> run -> task -> step),
per-run budgets that halt runaway agents mid-flight, and a step router
that sends mechanical steps to a cheap model tier.

## Stack

- Python 3; package `agentledger/`, sample workload in `sample_agent/`
  (10-task / 31-step ops suite on deterministic stub models — no API
  keys, no network). Spans stored in local SQLite, exportable as OTLP
  JSON.

## Tests

```bash
pytest
```

## Architecture notes

- Spans follow the OpenTelemetry GenAI semantic conventions. Attribution
  granularity (agent -> run -> task -> step) is the contract — never
  emit a billable step without its full parent chain.
- `Ledger(..., external_trace_id=...)` stamps `agenttrace.trace_id` on
  the ROOT span only, so ledger spans can join an AgentTrace fleet
  trace. OTLP trace identity itself is never rewritten.
- Budget checks happen BEFORE the call that would breach the ceiling;
  when a budget bites, the halt and its reason are written into the
  run's own trace.
- Reported costs must reproduce exactly from the stub models — if a
  change alters a number in the README tables, regenerate and explain.
- `runs/*.json` are regenerable artifacts, not source; don't hand-edit.

## Shared rules

- Use Unix LF line endings in every file; never CRLF.
- Never commit secrets, tokens, or credentials — real or synthetic-looking.
- Tests must pass before you describe a change as complete; run the test
  command above and report honestly if you cannot.
- Prefer the smallest complete implementation: reuse what already exists in
  this repo before adding new code, files, or dependencies.
