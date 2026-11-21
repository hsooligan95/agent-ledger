"""Pinned, dated price table.

Prices are illustrative list prices for two model *tiers*, pinned on
PRICE_TABLE_DATE so every report in this repo is reproducible. They are
not live prices and will drift from any provider's real pricing — that is
the point of pinning them: cost numbers in the README and reports were
computed with exactly this table.
"""

from __future__ import annotations

PRICE_TABLE_DATE = "2026-11-20"

# USD per 1,000,000 tokens.
PRICE_TABLE: dict[str, dict[str, float]] = {
    # Frontier tier (GPT-4 / Claude Opus class list prices, illustrative).
    "frontier": {"input_per_mtok": 15.00, "output_per_mtok": 75.00},
    # Cheap tier (GPT-4o-mini / Haiku class list prices, illustrative).
    "cheap": {"input_per_mtok": 0.15, "output_per_mtok": 0.60},
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Cost of one call. Raises KeyError for an unknown model — fail loud."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")
    p = PRICE_TABLE[model]
    return (
        input_tokens * p["input_per_mtok"] + output_tokens * p["output_per_mtok"]
    ) / 1_000_000.0
