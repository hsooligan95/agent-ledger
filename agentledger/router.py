"""Step classification and model routing.

A step is EASY when it is mechanical — extraction, classification,
formatting — work a cheap model does as reliably as a frontier model.
Everything else (reasoning, planning, synthesis, judgment) is HARD and
goes to the frontier tier. The router is deliberately a small explicit
table, not a learned classifier: routing decisions should be auditable.
"""

from __future__ import annotations

EASY_STEP_KINDS = frozenset({"extract", "classify", "format"})
HARD_STEP_KINDS = frozenset({"reason", "plan", "synthesize", "judge"})

FRONTIER = "frontier"
CHEAP = "cheap"


def classify_step(step_kind: str) -> str:
    """Return 'easy' or 'hard' for a step kind. Unknown kinds are HARD —
    when in doubt, spend the money; a misrouted reasoning step costs more
    in wrong answers than it saves in tokens."""
    kind = step_kind.strip().lower()
    if kind in EASY_STEP_KINDS:
        return "easy"
    return "hard"


def route(step_kind: str) -> str:
    """Model tier for a step kind under the routing policy."""
    return CHEAP if classify_step(step_kind) == "easy" else FRONTIER
