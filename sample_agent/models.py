"""Deterministic stub model backends — NO API keys, NO network.

Two tiers, "frontier" and "cheap". Both execute the mechanical step
kinds (extract / classify / format) identically and correctly. They
differ on "reason" steps: the frontier stub evaluates feasibility and
picks the cheapest feasible option; the cheap stub naively picks the
first option. That single difference is what makes routing safe to
demonstrate: send reasoning to the cheap tier and answers get worse;
route it properly and outcomes are identical at a fraction of the cost.

Token counts and latencies are deterministic functions of the prompt
(hash-seeded), so runs are byte-for-byte reproducible. They are
simulated values, labeled as such everywhere they appear.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelResult:
    output: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16)


def _extract(payload: dict) -> str:
    m = re.search(payload["pattern"], payload["text"])
    return m.group(1) if m else ""


def _classify(payload: dict) -> str:
    text = payload["text"].lower()
    best_label, best_hits = "", -1
    for label, keywords in payload["labels"].items():
        hits = sum(1 for kw in keywords if kw.lower() in text)
        if hits > best_hits:
            best_label, best_hits = label, hits
    return best_label


def _format(payload: dict, context: str) -> str:
    record = {
        "value": context,
        "currency": "USD",
        "source": "ops-ledger",
        "internal_note": "do-not-export",
    }
    return json.dumps({k: record[k] for k in payload["fields"]})


def _reason(payload: dict, model: str) -> str:
    options = payload["options"]
    if model == "cheap":
        return options[0]["name"]  # naive: first option, feasible or not
    feasible = [o for o in options if o["feasible"]]
    return min(feasible, key=lambda o: o["cost"])["name"]


class StubModel:
    """Stands in for an LLM API. Same inputs -> same outputs, always."""

    def invoke(self, *, model: str, step_kind: str, name: str,
               payload: dict, context: str = "") -> ModelResult:
        prompt = json.dumps(
            {"step": name, "payload": payload, "context": context}, sort_keys=True
        )
        input_tokens = 300 + len(prompt) // 2
        d = _seed(model, prompt)

        if step_kind == "extract":
            output, out_tok, latency = _extract(payload), 30 + d % 40, 120 + d % 80
        elif step_kind == "classify":
            output, out_tok, latency = _classify(payload), 10 + d % 15, 90 + d % 60
        elif step_kind == "format":
            output, out_tok, latency = _format(payload, context), 60 + d % 60, 110 + d % 70
        elif step_kind == "reason":
            output = _reason(payload, model)
            out_tok, latency = 400 + d % 300, 900 + d % 400
        else:
            raise ValueError(f"unknown step kind: {step_kind!r}")

        return ModelResult(
            output=output,
            input_tokens=input_tokens,
            output_tokens=out_tok,
            latency_ms=float(latency),
        )
