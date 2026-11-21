"""LangGraph agents, instrumented with AgentLedger.

Two graphs:

- build_agent: the sample ops agent. Walks a task's step chain; each
  step is one Ledger step span wrapping one stub-model call. In
  "baseline" mode every step runs on the frontier tier; in "routed"
  mode agentledger.router picks the tier per step kind.

- build_runaway_agent: a refine loop that never converges — each pass
  appends to the draft, so prompts (and cost) grow every iteration. It
  stops only when something stops it. That something is the budget.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agentledger import Ledger, route

from .models import StubModel


class AgentState(TypedDict):
    task: dict
    mode: str  # "baseline" | "routed"
    step_index: int
    context: str
    outputs: list[str]


def build_agent(ledger: Ledger, model: StubModel):
    def do_step(state: AgentState) -> dict:
        step = state["task"]["steps"][state["step_index"]]
        tier = "frontier" if state["mode"] == "baseline" else route(step["kind"])
        with ledger.step(step["name"], kind=step["kind"]):
            result = model.invoke(
                model=tier,
                step_kind=step["kind"],
                name=step["name"],
                payload=step["payload"],
                context=state["context"],
            )
            ledger.record_usage(
                model=tier,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
            )
        return {
            "step_index": state["step_index"] + 1,
            "context": result.output,
            "outputs": state["outputs"] + [result.output],
        }

    def next_node(state: AgentState) -> str:
        return "step" if state["step_index"] < len(state["task"]["steps"]) else END

    graph = StateGraph(AgentState)
    graph.add_node("step", do_step)
    graph.add_edge(START, "step")
    graph.add_conditional_edges("step", next_node, {"step": "step", END: END})
    return graph.compile()


class LoopState(TypedDict):
    iteration: int
    context: str


_RUNAWAY_OPTIONS = [
    {"name": "ship-it", "cost": 5, "feasible": False},
    {"name": "revise", "cost": 40, "feasible": True},
    {"name": "escalate", "cost": 90, "feasible": True},
]


def build_runaway_agent(ledger: Ledger, model: StubModel):
    """A self-looping 'refine forever' agent. No exit edge: the only ways
    out are the graph recursion limit or a BudgetExceeded from the Ledger."""

    def refine(state: LoopState) -> dict:
        name = f"refine-{state['iteration']}"
        payload = {"options": _RUNAWAY_OPTIONS, "draft": state["context"]}
        with ledger.step(name, kind="reason"):
            result = model.invoke(
                model="frontier",
                step_kind="reason",
                name=name,
                payload=payload,
                context=state["context"],
            )
            ledger.record_usage(
                model="frontier",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
            )
        # The draft grows every pass, so the next prompt costs more.
        return {
            "iteration": state["iteration"] + 1,
            "context": state["context"] + f" [pass {state['iteration']}: {result.output}]",
        }

    graph = StateGraph(LoopState)
    graph.add_node("refine", refine)
    graph.add_edge(START, "refine")
    graph.add_edge("refine", "refine")
    return graph.compile()
