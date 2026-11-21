"""SQLite span store, cost rollups, and OTLP JSON export.

Spans are written by the Ledger's span processor (tracer.py) into a
plain SQLite file — no server, no account. Rollups are pure SQL over
that file, so any report can be regenerated from the stored spans alone.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS spans (
    span_id     TEXT PRIMARY KEY,
    trace_id    TEXT NOT NULL,
    parent_id   TEXT,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,             -- run | task | step
    agent       TEXT,
    run_id      TEXT,
    task_id     TEXT,
    step_name   TEXT,
    model       TEXT,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL    NOT NULL DEFAULT 0,
    latency_ms    REAL    NOT NULL DEFAULT 0,
    status        TEXT    NOT NULL DEFAULT 'ok',  -- ok | budget_exceeded | error
    halt_reason   TEXT,
    start_ns      INTEGER NOT NULL,
    end_ns        INTEGER NOT NULL,
    attributes    TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_spans_run ON spans(run_id);
CREATE INDEX IF NOT EXISTS idx_spans_task ON spans(run_id, task_id);
"""


class SpanStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def insert_span(self, row: dict) -> None:
        cols = ", ".join(row.keys())
        marks = ", ".join("?" for _ in row)
        self._conn.execute(
            f"INSERT OR REPLACE INTO spans ({cols}) VALUES ({marks})",
            list(row.values()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- rollups ---------------------------------------------------------

    def rollup_by_task(self, run_id: str) -> list[dict]:
        """One row per task in a run: step count, tokens, cost, latency."""
        rows = self._conn.execute(
            """
            SELECT task_id,
                   COUNT(*)              AS steps,
                   SUM(input_tokens)     AS input_tokens,
                   SUM(output_tokens)    AS output_tokens,
                   SUM(cost_usd)         AS cost_usd,
                   SUM(latency_ms)       AS latency_ms,
                   SUM(CASE WHEN status = 'budget_exceeded' THEN 1 ELSE 0 END)
                                         AS budget_kills
            FROM spans
            WHERE run_id = ? AND kind = 'step'
            GROUP BY task_id
            ORDER BY task_id
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def rollup_by_run(self, run_id: str) -> dict:
        """Totals for a whole run (step spans only)."""
        row = self._conn.execute(
            """
            SELECT COUNT(*)            AS steps,
                   COUNT(DISTINCT task_id) AS tasks,
                   SUM(input_tokens)   AS input_tokens,
                   SUM(output_tokens)  AS output_tokens,
                   SUM(cost_usd)       AS cost_usd,
                   SUM(latency_ms)     AS latency_ms
            FROM spans
            WHERE run_id = ? AND kind = 'step'
            """,
            (run_id,),
        ).fetchone()
        return dict(row)

    def run_status(self, run_id: str) -> dict:
        """Run-level span info: status and halt reason, if the run was killed."""
        row = self._conn.execute(
            "SELECT status, halt_reason FROM spans WHERE run_id = ? AND kind = 'run'",
            (run_id,),
        ).fetchone()
        return dict(row) if row else {"status": "unknown", "halt_reason": None}

    def run_ids(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT run_id FROM spans WHERE run_id IS NOT NULL ORDER BY run_id"
        ).fetchall()
        return [r["run_id"] for r in rows]

    # -- export ----------------------------------------------------------

    def export_otlp_json(self, path: str | Path, run_id: str | None = None) -> Path:
        """Write spans as OTLP JSON (the format Jaeger and OTel collectors
        ingest). GenAI attributes ride along under their standard keys."""
        query = "SELECT * FROM spans"
        params: tuple = ()
        if run_id is not None:
            query += " WHERE run_id = ?"
            params = (run_id,)
        query += " ORDER BY start_ns"
        rows = [dict(r) for r in self._conn.execute(query, params).fetchall()]

        spans = []
        for r in rows:
            attrs = json.loads(r["attributes"])
            attrs.update({
                "agentledger.kind": r["kind"],
                "agentledger.cost_usd": r["cost_usd"],
                "agentledger.latency_ms": r["latency_ms"],
            })
            if r["task_id"]:
                attrs["agentledger.task_id"] = r["task_id"]
            if r["run_id"]:
                attrs["agentledger.run_id"] = r["run_id"]
            spans.append({
                "traceId": r["trace_id"],
                "spanId": r["span_id"],
                "parentSpanId": r["parent_id"] or "",
                "name": r["name"],
                "kind": 1,  # SPAN_KIND_INTERNAL
                "startTimeUnixNano": str(r["start_ns"]),
                "endTimeUnixNano": str(r["end_ns"]),
                "attributes": [
                    {"key": k, "value": _otlp_value(v)} for k, v in attrs.items()
                ],
                "status": {"code": 2 if r["status"] != "ok" else 1},
            })

        doc = {
            "resourceSpans": [{
                "resource": {
                    "attributes": [
                        {"key": "service.name",
                         "value": {"stringValue": "agentledger"}}
                    ]
                },
                "scopeSpans": [{
                    "scope": {"name": "agentledger", "version": "0.1.0"},
                    "spans": spans,
                }],
            }]
        }
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return out


def _otlp_value(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": str(v)}
