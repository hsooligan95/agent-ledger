"""Static reports from stored spans.

Regenerates reports/report.md and reports/report.html from the three
experiment databases in runs/ (baseline, routed, runaway). Every number
comes from SQL rollups over the recorded spans — nothing is hand-typed.

    python -m agentledger.report            # writes reports/report.{md,html}
"""

from __future__ import annotations

import html
from pathlib import Path

from .pricing import PRICE_TABLE_DATE
from .store import SpanStore

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
REPORTS_DIR = ROOT / "reports"

RUN_IDS = {"baseline": "baseline", "routed": "routed", "runaway": "runaway"}


def _load(mode: str) -> tuple[SpanStore, dict, list[dict], dict]:
    store = SpanStore(RUNS_DIR / f"{mode}.db")
    run_id = RUN_IDS[mode]
    return store, store.rollup_by_run(run_id), store.rollup_by_task(run_id), store.run_status(run_id)


def _money(x: float) -> str:
    return f"${x:.6f}"


def build_report() -> tuple[str, str]:
    base_store, base, base_tasks, _ = _load("baseline")
    routed_store, routed, routed_tasks, _ = _load("routed")
    run_store, runaway, runaway_tasks, runaway_status = _load("runaway")

    savings = base["cost_usd"] - routed["cost_usd"]
    savings_pct = (savings / base["cost_usd"] * 100.0) if base["cost_usd"] else 0.0

    base_by_task = {t["task_id"]: t for t in base_tasks}
    routed_by_task = {t["task_id"]: t for t in routed_tasks}
    task_ids = sorted(set(base_by_task) | set(routed_by_task))

    # ---- markdown ----
    md: list[str] = []
    md.append("# AgentLedger — experiment report")
    md.append("")
    md.append(f"Regenerated from stored spans. Price table pinned {PRICE_TABLE_DATE} "
              "(illustrative; see agentledger/pricing.py). Token counts and latencies "
              "are deterministic stub values — see README limitations.")
    md.append("")
    md.append("## Baseline (all steps on frontier) vs routed (easy steps on cheap)")
    md.append("")
    md.append("| Task | Baseline cost | Routed cost | Saved | Baseline tokens (in/out) | Routed tokens (in/out) |")
    md.append("|---|---|---|---|---|---|")
    for tid in task_ids:
        b = base_by_task.get(tid, {})
        r = routed_by_task.get(tid, {})
        md.append(
            f"| {tid} | {_money(b.get('cost_usd', 0))} | {_money(r.get('cost_usd', 0))} "
            f"| {_money(b.get('cost_usd', 0) - r.get('cost_usd', 0))} "
            f"| {b.get('input_tokens', 0)}/{b.get('output_tokens', 0)} "
            f"| {r.get('input_tokens', 0)}/{r.get('output_tokens', 0)} |"
        )
    md.append(
        f"| **Total** | **{_money(base['cost_usd'])}** | **{_money(routed['cost_usd'])}** "
        f"| **{_money(savings)} ({savings_pct:.1f}%)** "
        f"| **{base['input_tokens']}/{base['output_tokens']}** "
        f"| **{routed['input_tokens']}/{routed['output_tokens']}** |"
    )
    md.append("")
    md.append(f"Routing saved **{savings_pct:.1f}%** of spend "
              f"({_money(base['cost_usd'])} -> {_money(routed['cost_usd'])}) across "
              f"{base['tasks']} tasks / {base['steps']} steps, with identical task "
              "outcomes (success is asserted by the run harness, not assumed).")
    md.append("")
    md.append("## Runaway run (budget enforcement)")
    md.append("")
    md.append(f"- Status: **{runaway_status['status']}**")
    md.append(f"- Halt reason recorded in trace: {runaway_status['halt_reason']}")
    md.append(f"- Steps completed before the kill: {runaway['steps']}")
    md.append(f"- Spend at halt: {_money(runaway['cost_usd'])} "
              f"({runaway['input_tokens']} in / {runaway['output_tokens']} out tokens)")
    md.append("")
    md.append("Per-task detail:")
    md.append("")
    md.append("| Task | Steps | Cost | Budget kills |")
    md.append("|---|---|---|---|")
    for t in runaway_tasks:
        md.append(f"| {t['task_id']} | {t['steps']} | {_money(t['cost_usd'])} | {t['budget_kills']} |")
    md.append("")

    # ---- html ----
    rows = ""
    for tid in task_ids:
        b = base_by_task.get(tid, {})
        r = routed_by_task.get(tid, {})
        rows += (
            f"<tr><td>{html.escape(tid)}</td><td>{_money(b.get('cost_usd', 0))}</td>"
            f"<td>{_money(r.get('cost_usd', 0))}</td>"
            f"<td>{_money(b.get('cost_usd', 0) - r.get('cost_usd', 0))}</td></tr>"
        )
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>AgentLedger — experiment report</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;max-width:56rem}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:.35rem .6rem;text-align:right}}
td:first-child,th:first-child{{text-align:left}}</style></head>
<body><h1>AgentLedger — experiment report</h1>
<p>Price table pinned {PRICE_TABLE_DATE} (illustrative). Numbers regenerated
from stored spans; token counts and latencies are deterministic stub values.</p>
<h2>Baseline vs routed</h2>
<table><tr><th>Task</th><th>Baseline</th><th>Routed</th><th>Saved</th></tr>{rows}
<tr><th>Total</th><th>{_money(base['cost_usd'])}</th><th>{_money(routed['cost_usd'])}</th>
<th>{_money(savings)} ({savings_pct:.1f}%)</th></tr></table>
<h2>Runaway run</h2>
<p>Status: <strong>{html.escape(runaway_status['status'])}</strong><br>
Halt reason: {html.escape(runaway_status['halt_reason'] or '')}<br>
Steps before kill: {runaway['steps']} &middot; spend at halt: {_money(runaway['cost_usd'])}</p>
</body></html>
"""
    for s in (base_store, routed_store, run_store):
        s.close()
    return "\n".join(md) + "\n", page


def main() -> None:
    md, page = build_report()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "report.md").write_text(md, encoding="utf-8")
    (REPORTS_DIR / "report.html").write_text(page, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
