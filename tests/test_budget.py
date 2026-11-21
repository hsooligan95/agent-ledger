"""Budget cutoff behavior: ceilings bite, and the kill lands in the trace."""

import pytest

from agentledger import BudgetExceeded, BudgetLimits, Ledger, SpanStore


def _drive_until_halt(ledger: Ledger, run_id: str, task_id: str,
                      per_call: tuple[int, int], max_calls: int = 50) -> int:
    """Record identical frontier calls until BudgetExceeded. Returns the
    number of calls recorded (including the breaching one)."""
    calls = 0
    with ledger.run(run_id):
        with ledger.task(task_id):
            for i in range(max_calls):
                with ledger.step(f"call-{i}", kind="reason"):
                    calls += 1
                    ledger.record_usage(
                        model="frontier", input_tokens=per_call[0],
                        output_tokens=per_call[1], latency_ms=10.0,
                    )
    return calls


def test_per_run_budget_halts_and_is_recorded(tmp_path):
    db = tmp_path / "spans.db"
    # One call: 1000 in / 500 out on frontier = $0.0525. Budget $0.10 fits
    # exactly one call; the second call must raise.
    ledger = Ledger(db, agent_name="t", budget=BudgetLimits(per_run_usd=0.10))
    with pytest.raises(BudgetExceeded) as excinfo:
        _drive_until_halt(ledger, "run-x", "task-x", (1000, 500))
    ledger.shutdown()

    assert excinfo.value.scope == "run"
    assert excinfo.value.limit_usd == 0.10

    store = SpanStore(db)
    status = store.run_status("run-x")
    assert status["status"] == "budget_exceeded"
    assert "Budget exceeded" in status["halt_reason"]
    by_task = store.rollup_by_task("run-x")
    assert by_task[0]["steps"] == 2            # both calls recorded
    assert by_task[0]["budget_kills"] == 1     # exactly one marked as the kill
    store.close()


def test_per_task_budget_scopes_to_the_task(tmp_path):
    db = tmp_path / "spans.db"
    # Per-task $0.06: one $0.0525 call fits per task; a second in the SAME
    # task raises, but the exception must name the task scope.
    ledger = Ledger(db, agent_name="t", budget=BudgetLimits(per_task_usd=0.06))
    with pytest.raises(BudgetExceeded) as excinfo:
        _drive_until_halt(ledger, "run-y", "task-y", (1000, 500))
    assert excinfo.value.scope == "task"
    assert excinfo.value.task_id == "task-y"
    ledger.shutdown()


def test_no_budget_never_halts(tmp_path):
    db = tmp_path / "spans.db"
    ledger = Ledger(db, agent_name="t")  # BudgetLimits() -> no ceilings
    calls = _drive_until_halt(ledger, "run-z", "task-z", (1000, 500), max_calls=5)
    ledger.shutdown()
    assert calls == 5
    store = SpanStore(db)
    assert store.run_status("run-z")["status"] == "ok"
    store.close()


def test_invalid_budget_rejected():
    with pytest.raises(ValueError):
        BudgetLimits(per_run_usd=0)
    with pytest.raises(ValueError):
        BudgetLimits(per_task_usd=-1.0)
