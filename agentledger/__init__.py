"""AgentLedger — FinOps for AI agents.

Every token accounted for: OpenTelemetry GenAI instrumentation with
per-agent / per-run / per-task / per-step cost attribution, budgets that
halt runs mid-flight, and a step router that sends mechanical work to a
cheap model tier. The library has no dependency on the sample agent in
sample_agent/ — import it, wrap your calls, done.
"""

from .budget import BudgetExceeded, BudgetLimits
from .pricing import PRICE_TABLE, PRICE_TABLE_DATE, cost_usd
from .router import classify_step, route
from .store import SpanStore
from .tracer import Ledger

__all__ = [
    "BudgetExceeded",
    "BudgetLimits",
    "Ledger",
    "PRICE_TABLE",
    "PRICE_TABLE_DATE",
    "SpanStore",
    "classify_step",
    "cost_usd",
    "route",
]

__version__ = "0.1.0"
