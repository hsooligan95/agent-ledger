"""Budget enforcement.

Budgets are checked *before* each LLM call is allowed to proceed, using
the run's recorded spend plus the call's estimated cost. When a call
would exceed a ceiling, BudgetExceeded is raised and the halt is written
to the trace by the Ledger (see tracer.py), so a killed run explains
itself in its own report.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetLimits:
    """Spend ceilings in USD. None means 'no ceiling on this axis'."""

    per_task_usd: float | None = None
    per_run_usd: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("per_task_usd", self.per_task_usd),
            ("per_run_usd", self.per_run_usd),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive or None")


class BudgetExceeded(Exception):
    """Raised when a call would exceed a budget ceiling."""

    def __init__(self, scope: str, limit_usd: float, spent_usd: float,
                 attempted_usd: float, task_id: str | None) -> None:
        self.scope = scope            # "task" or "run"
        self.limit_usd = limit_usd
        self.spent_usd = spent_usd
        self.attempted_usd = attempted_usd
        self.task_id = task_id
        where = f"task {task_id!r}" if scope == "task" else "run"
        super().__init__(
            f"Budget exceeded on {where}: limit ${limit_usd:.6f}, "
            f"already spent ${spent_usd:.6f}, attempted call ${attempted_usd:.6f} "
            f"would bring total to ${spent_usd + attempted_usd:.6f}."
        )


def check_budget(limits: BudgetLimits, *, task_spent: float, run_spent: float,
                 attempted: float, task_id: str | None) -> None:
    """Raise BudgetExceeded if `attempted` would breach either ceiling."""
    if limits.per_task_usd is not None and task_spent + attempted > limits.per_task_usd:
        raise BudgetExceeded("task", limits.per_task_usd, task_spent, attempted, task_id)
    if limits.per_run_usd is not None and run_spent + attempted > limits.per_run_usd:
        raise BudgetExceeded("run", limits.per_run_usd, run_spent, attempted, task_id)
