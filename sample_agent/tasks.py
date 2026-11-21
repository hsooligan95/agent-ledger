"""The sample task suite: 10 small ops tasks, 31 steps.

Each task is a chain of steps. Easy steps (extract / classify / format)
are mechanical; the reason steps carry the judgment. In every reason
step the first option is the cheapest but infeasible — the trap a naive
cheap-model answer falls into. `expected` is the task's final output
(the format step's JSON), asserted by the run harness.
"""

from __future__ import annotations

import json

FIELDS = ["value", "currency", "source"]


def _fmt(value: str) -> str:
    return json.dumps({"value": value, "currency": "USD", "source": "ops-ledger"})


TASKS: list[dict] = [
    {
        "id": "invoice-approval",
        "steps": [
            {"name": "extract-total", "kind": "extract", "payload": {
                "text": "Invoice #1042 from Northwind. Total due: $1250.00 by Friday.",
                "pattern": r"Total due: \$([0-9]+\.[0-9]{2})"}},
            {"name": "check-limit", "kind": "reason", "payload": {"options": [
                {"name": "auto-pay-discount", "cost": 1100, "feasible": False},
                {"name": "approve", "cost": 1250, "feasible": True},
                {"name": "escalate", "cost": 1400, "feasible": True}]}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("approve"),
    },
    {
        "id": "ticket-triage",
        "steps": [
            {"name": "classify-ticket", "kind": "classify", "payload": {
                "text": "My payment was charged twice and I want a refund.",
                "labels": {
                    "billing": ["refund", "charged", "payment", "invoice"],
                    "technical": ["crash", "error", "login"],
                    "shipping": ["delivery", "package", "tracking"]}}},
            {"name": "route-queue", "kind": "reason", "payload": {"options": [
                {"name": "tier1", "cost": 2, "feasible": False},
                {"name": "billing-specialists", "cost": 6, "feasible": True},
                {"name": "general", "cost": 4, "feasible": False}]}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("billing-specialists"),
    },
    {
        "id": "log-extraction",
        "steps": [
            {"name": "extract-error-code", "kind": "extract", "payload": {
                "text": "2026-11-20T09:14Z ERROR code=DB-4471 connection refused",
                "pattern": r"code=([A-Z]+-[0-9]+)"}},
            {"name": "classify-severity", "kind": "classify", "payload": {
                "text": "Database connection refused, all writes failing.",
                "labels": {
                    "sev1": ["all writes failing", "outage", "data loss"],
                    "sev2": ["degraded", "slow"],
                    "sev3": ["minor", "cosmetic"]}}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("sev1"),
    },
    {
        "id": "vendor-choice",
        "steps": [
            {"name": "extract-budget", "kind": "extract", "payload": {
                "text": "Approved budget ceiling: $900 per month for tooling.",
                "pattern": r"ceiling: \$([0-9]+)"}},
            {"name": "pick-vendor", "kind": "reason", "payload": {"options": [
                {"name": "vendor-a", "cost": 450, "feasible": False},
                {"name": "vendor-b", "cost": 820, "feasible": True},
                {"name": "vendor-c", "cost": 890, "feasible": True}]}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("vendor-b"),
    },
    {
        "id": "refund-decision",
        "steps": [
            {"name": "classify-sentiment", "kind": "classify", "payload": {
                "text": "I am furious, this is the third time it broke.",
                "labels": {
                    "angry": ["furious", "third time", "unacceptable"],
                    "neutral": ["okay", "fine"],
                    "happy": ["great", "love"]}}},
            {"name": "extract-order", "kind": "extract", "payload": {
                "text": "Order ORD-88312 placed on Nov 12, still not working.",
                "pattern": r"(ORD-[0-9]+)"}},
            {"name": "decide-refund", "kind": "reason", "payload": {"options": [
                {"name": "deny", "cost": 0, "feasible": False},
                {"name": "full-refund", "cost": 59, "feasible": True},
                {"name": "partial-refund", "cost": 30, "feasible": False}]}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("full-refund"),
    },
    {
        "id": "meeting-summary",
        "steps": [
            {"name": "extract-date", "kind": "extract", "payload": {
                "text": "Sync scheduled for 2026-12-03 at 10:00 in room 4.",
                "pattern": r"(\d{4}-\d{2}-\d{2})"}},
            {"name": "classify-type", "kind": "classify", "payload": {
                "text": "Quarterly planning and roadmap review.",
                "labels": {
                    "planning": ["planning", "roadmap"],
                    "incident": ["outage", "incident"],
                    "social": ["party", "lunch"]}}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("planning"),
    },
    {
        "id": "capacity-plan",
        "steps": [
            {"name": "extract-usage", "kind": "extract", "payload": {
                "text": "Current usage at 78 percent of quota and climbing.",
                "pattern": r"([0-9]+) percent"}},
            {"name": "pick-tier", "kind": "reason", "payload": {"options": [
                {"name": "tier-s", "cost": 100, "feasible": False},
                {"name": "tier-m", "cost": 240, "feasible": True},
                {"name": "tier-l", "cost": 400, "feasible": True}]}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("tier-m"),
    },
    {
        "id": "sla-check",
        "steps": [
            {"name": "classify-region", "kind": "classify", "payload": {
                "text": "Latency spike reported in the Frankfurt data center.",
                "labels": {
                    "eu": ["frankfurt", "berlin", "dublin"],
                    "us": ["oregon", "virginia"],
                    "asia": ["tokyo", "singapore"]}}},
            {"name": "pick-action", "kind": "reason", "payload": {"options": [
                {"name": "ignore", "cost": 0, "feasible": False},
                {"name": "failover", "cost": 150, "feasible": True},
                {"name": "monitor", "cost": 20, "feasible": False}]}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("failover"),
    },
    {
        "id": "expense-report",
        "steps": [
            {"name": "extract-amount", "kind": "extract", "payload": {
                "text": "Taxi receipt amount: $46.20, airport to office.",
                "pattern": r"amount: \$([0-9]+\.[0-9]{2})"}},
            {"name": "classify-category", "kind": "classify", "payload": {
                "text": "Taxi from airport to office.",
                "labels": {
                    "travel": ["taxi", "flight", "hotel"],
                    "meals": ["lunch", "dinner"],
                    "supplies": ["paper", "pens"]}}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("travel"),
    },
    {
        "id": "access-request",
        "steps": [
            {"name": "classify-risk", "kind": "classify", "payload": {
                "text": "Requesting production database write access.",
                "labels": {
                    "high": ["production", "write access", "admin"],
                    "low": ["read-only", "dashboard view"]}}},
            {"name": "decide-access", "kind": "reason", "payload": {"options": [
                {"name": "auto-approve", "cost": 1, "feasible": False},
                {"name": "manager-review", "cost": 10, "feasible": True},
                {"name": "deny", "cost": 2, "feasible": False}]}},
            {"name": "emit-record", "kind": "format", "payload": {"fields": FIELDS}},
        ],
        "expected": _fmt("manager-review"),
    },
]
