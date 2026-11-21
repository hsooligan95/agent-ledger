"""The Ledger: OpenTelemetry instrumentation + budget enforcement.

Usage is three context managers and one charge call::

    ledger = Ledger("spans.db", agent_name="ops-agent",
                    budget=BudgetLimits(per_task_usd=0.05, per_run_usd=0.50))
    with ledger.run("run-001"):
        with ledger.task("task-1"):
            with ledger.step("extract-total", kind="extract"):
                result = model.invoke(...)          # your LLM call
                ledger.record_usage(model="cheap",  # price + budget check
                                    input_tokens=result.input_tokens,
                                    output_tokens=result.output_tokens,
                                    latency_ms=result.latency_ms)
    ledger.shutdown()

Every span carries OpenTelemetry GenAI semantic-convention attributes
(gen_ai.request.model, gen_ai.usage.input_tokens, ...) plus agentledger.*
attributes for cost and attribution (agent -> run -> task -> step).
Finished spans are exported to a local SQLite store (store.py); nothing
leaves the machine.

Budget semantics: record_usage prices the call, then checks it against
the ceilings using spend recorded so far. If the call would breach a
ceiling, the span is marked budget_exceeded with the reason, the cost is
still recorded (the call did happen), BudgetExceeded is raised, and the
run/task spans are marked with the halt reason as the exception unwinds.
The step's result is the caller's to discard — the sample agent does.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

from .budget import BudgetExceeded, BudgetLimits, check_budget
from .pricing import cost_usd
from .store import SpanStore


class _StoreExporter(SpanExporter):
    """Writes finished OTel spans into the SQLite store."""

    def __init__(self, store: SpanStore) -> None:
        self._store = store

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        for s in spans:
            a = dict(s.attributes or {})
            status = a.get("agentledger.status")
            if status is None:
                status = "error" if s.status.status_code == StatusCode.ERROR else "ok"
            parent_id = None
            if s.parent is not None:
                parent_id = format(s.parent.span_id, "016x")
            self._store.insert_span({
                "span_id": format(s.context.span_id, "016x"),
                "trace_id": format(s.context.trace_id, "032x"),
                "parent_id": parent_id,
                "name": s.name,
                "kind": a.get("agentledger.kind", "step"),
                "agent": a.get("agentledger.agent"),
                "run_id": a.get("agentledger.run_id"),
                "task_id": a.get("agentledger.task_id"),
                "step_name": a.get("agentledger.step"),
                "model": a.get("gen_ai.request.model"),
                "input_tokens": int(a.get("gen_ai.usage.input_tokens", 0)),
                "output_tokens": int(a.get("gen_ai.usage.output_tokens", 0)),
                "cost_usd": float(a.get("agentledger.cost_usd", 0.0)),
                "latency_ms": float(a.get("agentledger.simulated_latency_ms", 0.0)),
                "status": status,
                "halt_reason": a.get("agentledger.halt_reason"),
                "start_ns": s.start_time or 0,
                "end_ns": s.end_time or 0,
                "attributes": _jsonable(a),
            })
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _jsonable(attrs: dict) -> str:
    import json

    return json.dumps({k: v for k, v in attrs.items()}, default=str)


class Ledger:
    def __init__(self, db_path: str | Path, agent_name: str = "agent",
                 budget: BudgetLimits | None = None) -> None:
        self.store = SpanStore(db_path)
        self.agent_name = agent_name
        self.budget = budget or BudgetLimits()
        self._provider = TracerProvider(
            resource=Resource.create({"service.name": "agentledger"})
        )
        self._provider.add_span_processor(SimpleSpanProcessor(_StoreExporter(self.store)))
        self._tracer = self._provider.get_tracer("agentledger", "0.1.0")
        self._stack: list[tuple[str, str, str | None]] = []  # (level, run_id, task_id)
        self._run_spent: dict[str, float] = {}
        self._task_spent: dict[tuple[str, str], float] = {}

    # -- context managers -------------------------------------------------

    @contextmanager
    def run(self, run_id: str):
        with self._tracer.start_as_current_span(f"run {run_id}") as span:
            span.set_attributes({
                "agentledger.kind": "run",
                "agentledger.agent": self.agent_name,
                "agentledger.run_id": run_id,
            })
            self._stack.append(("run", run_id, None))
            try:
                yield
            except BudgetExceeded as e:
                span.set_attributes({
                    "agentledger.status": "budget_exceeded",
                    "agentledger.halt_reason": str(e),
                })
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
            finally:
                self._stack.pop()

    @contextmanager
    def task(self, task_id: str):
        run_id, _ = self._current()
        with self._tracer.start_as_current_span(f"task {task_id}") as span:
            span.set_attributes({
                "agentledger.kind": "task",
                "agentledger.agent": self.agent_name,
                "agentledger.run_id": run_id,
                "agentledger.task_id": task_id,
            })
            self._stack.append(("task", run_id, task_id))
            try:
                yield
            except BudgetExceeded as e:
                span.set_attributes({
                    "agentledger.status": "budget_exceeded",
                    "agentledger.halt_reason": str(e),
                })
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
            finally:
                self._stack.pop()

    @contextmanager
    def step(self, name: str, kind: str):
        run_id, task_id = self._current()
        with self._tracer.start_as_current_span(f"step {name}") as span:
            span.set_attributes({
                "agentledger.kind": "step",
                "agentledger.agent": self.agent_name,
                "agentledger.run_id": run_id,
                "agentledger.task_id": task_id,
                "agentledger.step": name,
                "agentledger.step_kind": kind,
            })
            try:
                yield span
            except BudgetExceeded as e:
                span.set_attributes({
                    "agentledger.status": "budget_exceeded",
                    "agentledger.halt_reason": str(e),
                })
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    # -- charging -----------------------------------------------------------

    def record_usage(self, *, model: str, input_tokens: int, output_tokens: int,
                     latency_ms: float = 0.0) -> float:
        """Price a completed LLM call, check budgets, stamp the current
        (step) span with GenAI usage attributes. Returns the cost in USD.
        Raises BudgetExceeded if the call breaches a ceiling."""
        run_id, task_id = self._current()
        cost = cost_usd(model, input_tokens, output_tokens)
        span = trace.get_current_span()
        span.set_attributes({
            "gen_ai.system": "stub",
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": model,
            "gen_ai.usage.input_tokens": input_tokens,
            "gen_ai.usage.output_tokens": output_tokens,
            "agentledger.cost_usd": cost,
            "agentledger.simulated_latency_ms": latency_ms,
        })
        try:
            check_budget(
                self.budget,
                task_spent=self._task_spent.get((run_id, task_id), 0.0),
                run_spent=self._run_spent.get(run_id, 0.0),
                attempted=cost,
                task_id=task_id,
            )
        except BudgetExceeded as e:
            span.set_attributes({
                "agentledger.status": "budget_exceeded",
                "agentledger.halt_reason": str(e),
            })
            span.set_status(Status(StatusCode.ERROR, str(e)))
            self._add_spend(run_id, task_id, cost)
            raise
        self._add_spend(run_id, task_id, cost)
        return cost

    # -- internals ----------------------------------------------------------

    def _current(self) -> tuple[str, str | None]:
        if not self._stack:
            raise RuntimeError("record outside of a run context")
        _, run_id, task_id = self._stack[-1]
        return run_id, task_id

    def _add_spend(self, run_id: str, task_id: str | None, cost: float) -> None:
        self._run_spent[run_id] = self._run_spent.get(run_id, 0.0) + cost
        if task_id is not None:
            key = (run_id, task_id)
            self._task_spent[key] = self._task_spent.get(key, 0.0) + cost

    def shutdown(self) -> None:
        self._provider.shutdown()
        self.store.close()
