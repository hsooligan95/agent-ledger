# AgentLedger — experiment report

Regenerated from stored spans. Price table pinned 2026-11-20 (illustrative; see agentledger/pricing.py). Token counts and latencies are deterministic stub values — see README limitations.

## Baseline (all steps on frontier) vs routed (easy steps on cheap)

| Task | Baseline cost | Routed cost | Saved | Baseline tokens (in/out) | Routed tokens (in/out) |
|---|---|---|---|---|---|
| access-request | $0.078600 | $0.058536 | $0.020064 | 1175/813 | 1175/791 |
| capacity-plan | $0.059805 | $0.037994 | $0.021811 | 1132/571 | 1132/590 |
| expense-report | $0.027915 | $0.000286 | $0.027629 | 1136/145 | 1136/192 |
| invoice-approval | $0.078180 | $0.058352 | $0.019828 | 1157/811 | 1157/860 |
| log-extraction | $0.030225 | $0.000283 | $0.029942 | 1155/172 | 1155/183 |
| meeting-summary | $0.027375 | $0.000250 | $0.027125 | 1140/137 | 1140/132 |
| refund-decision | $0.085605 | $0.057070 | $0.028535 | 1562/829 | 1562/804 |
| sla-check | $0.060195 | $0.042625 | $0.017570 | 1178/567 | 1178/584 |
| ticket-triage | $0.060885 | $0.042055 | $0.018830 | 1209/570 | 1209/593 |
| vendor-choice | $0.064350 | $0.043351 | $0.020999 | 1140/630 | 1140/613 |
| **Total** | **$0.573135** | **$0.340802** | **$0.232333 (40.5%)** | **11984/5245** | **11984/5342** |

Routing saved **40.5%** of spend ($0.573135 -> $0.340802) across 10 tasks / 31 steps, with identical task outcomes (success is asserted by the run harness, not assumed).

## Runaway run (budget enforcement)

- Status: **budget_exceeded**
- Halt reason recorded in trace: Budget exceeded on run: limit $0.250000, already spent $0.240825, attempted call $0.046245 would bring total to $0.287070.
- Steps completed before the kill: 6
- Spend at halt: $0.287070 (2763 in / 3275 out tokens)

Per-task detail:

| Task | Steps | Cost | Budget kills |
|---|---|---|---|
| runaway-loop | 6 | $0.287070 | 1 |

