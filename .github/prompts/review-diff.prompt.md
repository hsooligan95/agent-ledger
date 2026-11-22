---
mode: agent
description: Review the current diff against agent-ledger's invariants
---

Review my current diff against this repo's invariants:

- Never emit a billable step without its full agent -> run -> task -> step parent chain.
- external_trace_id stamps agenttrace.trace_id on the ROOT span only; OTLP trace identity itself is never rewritten.
- Budget checks happen BEFORE the call that would breach the ceiling, and the halt plus its reason are written into the run's trace.
- Reported costs must reproduce exactly from the stub models; runs/*.json are regenerable artifacts, not source.

Flag every violation with file and line. Also flag any change that
alters a documented behavior contract (output shapes, exit codes,
event schemas, recorded artifacts) without updating the docs and
tests that describe it. No style nitpicks — correctness and contract
violations only.
