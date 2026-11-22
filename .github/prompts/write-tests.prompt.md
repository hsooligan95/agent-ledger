---
mode: agent
description: Write tests for a named module in agent-ledger
---

Write tests for the module I name, following this repo's existing test
style, layout, and fixtures. Cover the behavior the module documents,
including these invariants where they apply:

- Never emit a billable step without its full agent -> run -> task -> step parent chain.
- external_trace_id stamps agenttrace.trace_id on the ROOT span only; OTLP trace identity itself is never rewritten.
- Budget checks happen BEFORE the call that would breach the ceiling, and the halt plus its reason are written into the run's trace.

Then run the test suite:

    pytest

Show the result. Do not claim done unless the suite is green; if a
test cannot pass, say why instead of weakening the assertion.
