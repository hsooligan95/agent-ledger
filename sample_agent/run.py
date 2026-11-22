"""Run the three experiments and write their span databases.

    python -m sample_agent.run            # all three
    python -m sample_agent.run baseline   # just one

Modes:
  baseline — every step on the frontier tier.
  routed   — agentledger.router picks the tier (easy steps -> cheap).
  runaway  — the refine-forever agent under a $0.25 run budget.

Each mode writes runs/<mode>.db (spans) and runs/<mode>-otlp.json
(OTLP export). Task success is asserted against the suite's expected
outputs; a failed assertion fails the run loudly.

AgentTrace joining (emit-side, optional): pass ``--trace-id <id>`` or
set ``AGENTTRACE_TRACE_ID`` and every run's root span is stamped with
``agenttrace.trace_id=<id>``, so an AgentTrace ingestor can join these
spans to that external trace. Default (neither given): no stamp, and
the exports are exactly what they were before.

Instance identity (emit-side): the root span is also stamped with
``agenttrace.instance`` — the shared ``AGENT_INSTANCE`` env var, or
``default`` when unset — so fleet rollups can tell two processes of
this agent type apart.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from agentledger import BudgetExceeded, BudgetLimits, Ledger, SpanStore

from .agent import build_agent, build_runaway_agent
from .models import StubModel
from .tasks import TASKS

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
RUNAWAY_BUDGET_USD = 0.25


def _fresh_db(mode: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    db = RUNS_DIR / f"{mode}.db"
    if db.exists():
        db.unlink()
    return db


def _export(mode: str, db: Path) -> None:
    store = SpanStore(db)
    store.export_otlp_json(RUNS_DIR / f"{mode}-otlp.json", run_id=mode)
    store.close()


def run_suite(mode: str, trace_id: str | None = None,
              instance: str | None = None) -> dict[str, bool]:
    db = _fresh_db(mode)
    ledger = Ledger(db, agent_name="ops-agent", budget=BudgetLimits(per_run_usd=10.0),
                    external_trace_id=trace_id, instance=instance)
    app = build_agent(ledger, StubModel())
    results: dict[str, bool] = {}
    with ledger.run(mode):
        for task in TASKS:
            with ledger.task(task["id"]):
                final = app.invoke({
                    "task": task, "mode": mode, "step_index": 0,
                    "context": "", "outputs": [],
                })
            results[task["id"]] = final["context"] == task["expected"]
    ledger.shutdown()
    _export(mode, db)
    return results


def run_runaway(trace_id: str | None = None,
                instance: str | None = None) -> str:
    db = _fresh_db("runaway")
    ledger = Ledger(
        db, agent_name="ops-agent",
        budget=BudgetLimits(per_run_usd=RUNAWAY_BUDGET_USD),
        external_trace_id=trace_id, instance=instance,
    )
    app = build_runaway_agent(ledger, StubModel())
    halt: str | None = None
    try:
        with ledger.run("runaway"):
            with ledger.task("runaway-loop"):
                app.invoke(
                    {"iteration": 0, "context": "draft"},
                    config={"recursion_limit": 100000},
                )
    except BudgetExceeded as e:
        halt = str(e)
    ledger.shutdown()
    _export("runaway", db)
    if halt is None:
        raise AssertionError("runaway agent was NOT stopped by the budget")
    return halt


def _extract_trace_id(argv: list[str]) -> tuple[str | None, list[str]]:
    """Pull ``--trace-id <id>`` out of argv; env var is the fallback."""
    args = list(argv[1:])
    trace_id = os.environ.get("AGENTTRACE_TRACE_ID") or None
    if "--trace-id" in args:
        i = args.index("--trace-id")
        if i + 1 >= len(args):
            raise SystemExit("--trace-id needs a value")
        trace_id = args[i + 1]
        del args[i:i + 2]
    return trace_id, args


def main(argv: list[str]) -> int:
    trace_id, mode_args = _extract_trace_id(argv)
    # Instance identity for AgentTrace fleet rollups: the shared
    # AGENT_INSTANCE env var; "default" when unset.
    instance = os.environ.get("AGENT_INSTANCE") or "default"
    modes = mode_args or ["baseline", "routed", "runaway"]
    for mode in modes:
        if mode in ("baseline", "routed"):
            results = run_suite(mode, trace_id=trace_id, instance=instance)
            passed = sum(results.values())
            print(f"[{mode}] tasks passed: {passed}/{len(results)}")
            for task_id, ok in results.items():
                print(f"  {'PASS' if ok else 'FAIL'}  {task_id}")
            if passed != len(results):
                print(f"[{mode}] FAILING — see task list above", file=sys.stderr)
                return 1
        elif mode == "runaway":
            halt = run_runaway(trace_id=trace_id, instance=instance)
            print(f"[runaway] halted by budget: {halt}")
        else:
            print(f"unknown mode: {mode}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
