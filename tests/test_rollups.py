"""Cost attribution math: pricing and SQLite rollups."""

import pytest

from agentledger import Ledger, SpanStore, cost_usd


def test_cost_usd_math():
    # frontier: $15 / $75 per Mtok; cheap: $0.15 / $0.60 per Mtok.
    assert cost_usd("frontier", 1_000_000, 0) == pytest.approx(15.00)
    assert cost_usd("frontier", 0, 1_000_000) == pytest.approx(75.00)
    assert cost_usd("cheap", 1_000_000, 1_000_000) == pytest.approx(0.75)
    assert cost_usd("frontier", 0, 0) == 0.0


def test_cost_usd_rejects_bad_input():
    with pytest.raises(KeyError):
        cost_usd("no-such-model", 1, 1)
    with pytest.raises(ValueError):
        cost_usd("frontier", -1, 0)


def _record(ledger: Ledger, run_id: str, plan: dict[str, list[tuple[str, int, int]]]):
    """plan: task_id -> [(model, in_tokens, out_tokens), ...]"""
    with ledger.run(run_id):
        for task_id, calls in plan.items():
            with ledger.task(task_id):
                for i, (model, tin, tout) in enumerate(calls):
                    with ledger.step(f"step-{i}", kind="reason"):
                        ledger.record_usage(
                            model=model, input_tokens=tin,
                            output_tokens=tout, latency_ms=100.0,
                        )


def test_rollup_by_task_and_run(tmp_path):
    db = tmp_path / "spans.db"
    ledger = Ledger(db, agent_name="test-agent")
    _record(ledger, "r1", {
        "task-a": [("frontier", 1000, 500), ("cheap", 2000, 100)],
        "task-b": [("frontier", 4000, 2000)],
    })
    ledger.shutdown()

    store = SpanStore(db)
    by_task = {t["task_id"]: t for t in store.rollup_by_task("r1")}

    a = by_task["task-a"]
    assert a["steps"] == 2
    assert a["input_tokens"] == 3000
    assert a["output_tokens"] == 600
    expected_a = cost_usd("frontier", 1000, 500) + cost_usd("cheap", 2000, 100)
    assert a["cost_usd"] == pytest.approx(expected_a)
    assert a["latency_ms"] == pytest.approx(200.0)

    b = by_task["task-b"]
    assert b["steps"] == 1
    assert b["cost_usd"] == pytest.approx(cost_usd("frontier", 4000, 2000))

    run = store.rollup_by_run("r1")
    assert run["steps"] == 3
    assert run["tasks"] == 2
    assert run["input_tokens"] == 7000
    assert run["output_tokens"] == 2600
    assert run["cost_usd"] == pytest.approx(expected_a + b["cost_usd"])
    store.close()


def test_rollups_are_per_run(tmp_path):
    db = tmp_path / "spans.db"
    ledger = Ledger(db, agent_name="test-agent")
    _record(ledger, "r1", {"t": [("cheap", 100, 100)]})
    _record(ledger, "r2", {"t": [("frontier", 100, 100)]})
    ledger.shutdown()

    store = SpanStore(db)
    assert store.rollup_by_run("r1")["cost_usd"] == pytest.approx(cost_usd("cheap", 100, 100))
    assert store.rollup_by_run("r2")["cost_usd"] == pytest.approx(cost_usd("frontier", 100, 100))
    assert store.run_ids() == ["r1", "r2"]
    store.close()
