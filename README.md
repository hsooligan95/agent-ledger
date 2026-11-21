# AgentLedger — FinOps for AI Agents

**Every token accounted for.**

Agents don't fail loudly on cost — they fail on the invoice. AgentLedger is an observability and control layer for LangGraph agents that answers three questions most agent stacks can't:

1. **What did that cost?** — OpenTelemetry spans with GenAI semantic-convention attributes, attributing tokens, cost, and latency to **agent → run → task → step**, stored locally in SQLite and exportable as OTLP JSON (the format Jaeger and OTel collectors ingest).
2. **What stops a runaway agent?** — Per-task and per-run **budgets that bite**: when a call would breach a ceiling, the run is halted mid-flight and the reason is written into its own trace.
3. **Where is money being wasted?** — A **step router** sends mechanical steps (extraction, classification, formatting) to a cheap model tier and reserves the frontier tier for reasoning. Measured below: **40.5% cheaper, identical outcomes.**

## The experiments (real runs, reproducible)

The sample agent (`sample_agent/`) runs a 10-task / 31-step ops suite on deterministic stub models — no API keys, no network. Task success is asserted against expected outputs by the harness, not assumed.

### Baseline vs routed

| Task | Baseline cost | Routed cost | Saved |
|---|---|---|---|
| access-request | $0.078600 | $0.058536 | $0.020064 |
| capacity-plan | $0.059805 | $0.037994 | $0.021811 |
| expense-report | $0.027915 | $0.000286 | $0.027629 |
| invoice-approval | $0.078180 | $0.058352 | $0.019828 |
| log-extraction | $0.030225 | $0.000283 | $0.029942 |
| meeting-summary | $0.027375 | $0.000250 | $0.027125 |
| refund-decision | $0.085605 | $0.057070 | $0.028535 |
| sla-check | $0.060195 | $0.042625 | $0.017570 |
| ticket-triage | $0.060885 | $0.042055 | $0.018830 |
| vendor-choice | $0.064350 | $0.043351 | $0.020999 |
| **Total** | **$0.573135** | **$0.340802** | **$0.232333 (40.5%)** |

Both modes passed **10/10 tasks**. Tasks made only of easy steps (expense-report, log-extraction, meeting-summary) got ~99% cheaper; tasks dominated by a reasoning step saved less — which is exactly the honest shape of routing gains. Full per-task token detail: [`reports/report.md`](reports/report.md) / [`reports/report.html`](reports/report.html).

### Runaway run — budget enforcement

A "refine forever" agent (each pass grows the draft, so each pass costs more) under a **$0.25 run budget**:

- Status: **budget_exceeded**
- Steps completed before the kill: **6**
- Spend at halt: **$0.287070** (the breaching call is recorded, then the run stops)
- Halt reason, recorded in the trace itself: *"Budget exceeded on run: limit $0.250000, already spent $0.240825, attempted call $0.046245 would bring total to $0.287070."*

Without the budget, that loop runs to the graph recursion limit. With it, the run dies at 6 steps and explains itself.

## Instrument your own agent

The `agentledger` package has **no dependency on the sample agent** — import it, wrap your calls, done:

```python
from agentledger import BudgetLimits, Ledger

ledger = Ledger("spans.db", agent_name="ops-agent",
                budget=BudgetLimits(per_task_usd=0.05, per_run_usd=0.50))

with ledger.run("run-001"):
    with ledger.task("task-1"):
        with ledger.step("extract-total", kind="extract"):
            result = your_llm_call(...)            # any provider
            ledger.record_usage(                   # pricing + budget check
                model="cheap",
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                latency_ms=result.latency_ms,
            )
ledger.shutdown()
```

Then query the store (`SpanStore.rollup_by_task` / `rollup_by_run`) or export OTLP JSON (`SpanStore.export_otlp_json`) for Jaeger/collector ingestion. Routing is one function: `agentledger.route(step_kind)` → `"cheap"` or `"frontier"`.

## Layout

```
agentledger/     the library (pricing, budget, router, tracer, store, report)
sample_agent/    demo: LangGraph ops agent + stub models + 10-task suite
tests/           pricing/rollup math, budget cutoff, router classification
runs/            span DBs + OTLP exports from the latest experiment runs
reports/         report.md / report.html, regenerated from stored spans
```

## Quickstart

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest            # 12 tests
.venv/bin/python -m sample_agent.run  # baseline + routed + runaway
.venv/bin/python -m agentledger.report
```

Verified end-to-end in a fresh venv from the pinned `requirements.txt`: 12/12 tests pass, baseline 10/10 tasks, routed 10/10 tasks, runaway halted by budget.

## Price table

Prices live in `agentledger/pricing.py`, **pinned on 2026-11-20** and labeled illustrative: frontier tier $15.00 / $75.00 per Mtok (in/out), cheap tier $0.15 / $0.60 per Mtok. They are representative list prices for the two tiers, not live quotes — pinning them is what makes every number in this repo reproducible.

## Honest limitations

- **Stub models.** Token counts and latencies are deterministic functions of the prompt, not measurements of a real provider. The accounting, routing, and budget machinery is real; the meter readings are simulated. Wiring a real provider means implementing the same `invoke` shape and passing real usage numbers to `record_usage`.
- **The cheap stub is deliberately naive at reasoning** (it picks the first option). That models a real failure mode — small models shortcutting judgment calls — but real accuracy deltas will differ per model and task.
- **Budget enforcement point.** A call is priced when it completes; the breaching call is recorded and its result discarded, and no further steps run. A production variant would also pre-check with an estimated cost before dispatch.
- **Single-process, local SQLite.** No server, no auth, no multi-writer support. The OTLP export is the bridge to a real observability stack.
- **Routing is a static table**, not a learned classifier — deliberate: routing decisions should be auditable. Unknown step kinds route to the frontier tier (spend money before losing accuracy).

## License

MIT — see [LICENSE](LICENSE).
