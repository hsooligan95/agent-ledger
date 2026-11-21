"""AgentTrace joining: the external trace ID stamp (emit-side only).

With ``external_trace_id`` set, each run's ROOT span carries
``agenttrace.trace_id`` in the OTLP export, so an AgentTrace ingestor
can join the run's spans to that external trace. The spans' OTLP trace
identity is unchanged. Without it, no stamp appears anywhere.
"""

import json

from agentledger import Ledger, SpanStore


def _run_one(tmp_path, external_trace_id=None):
    db = tmp_path / "spans.db"
    ledger = Ledger(db, agent_name="test-agent",
                    external_trace_id=external_trace_id)
    with ledger.run("r1"):
        with ledger.task("t1"):
            with ledger.step("s1", kind="reason"):
                ledger.record_usage(model="cheap", input_tokens=100,
                                    output_tokens=50, latency_ms=10.0)
    ledger.shutdown()
    out = tmp_path / "export.json"
    store = SpanStore(db)
    store.export_otlp_json(out, run_id="r1")
    store.close()
    doc = json.loads(out.read_text(encoding="utf-8"))
    return [s for rs in doc["resourceSpans"] for ss in rs["scopeSpans"]
            for s in ss["spans"]]


def _attrs(span):
    return {a["key"]: next(iter(a["value"].values()))
            for a in span["attributes"]}


def test_external_trace_id_stamped_on_root_span_only(tmp_path):
    spans = _run_one(tmp_path, external_trace_id="trace-drill-abc")
    by_kind = {}
    for span in spans:
        by_kind.setdefault(_attrs(span)["agentledger.kind"], []).append(span)
    root = by_kind["run"][0]
    assert _attrs(root)["agenttrace.trace_id"] == "trace-drill-abc"
    for kind in ("task", "step"):
        for span in by_kind[kind]:
            assert "agenttrace.trace_id" not in _attrs(span)
    # OTLP identity untouched: one native trace ID across all spans.
    assert len({s["traceId"] for s in spans}) == 1
    assert spans[0]["traceId"] != "trace-drill-abc"


def test_no_stamp_by_default(tmp_path):
    spans = _run_one(tmp_path)
    for span in spans:
        assert "agenttrace.trace_id" not in _attrs(span)
