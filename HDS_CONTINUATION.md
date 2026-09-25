# HDS Continuation State

This file records the current execution handoff for coding agents.

## Branch
hds-scientific-provenance

## Mission
Build HDS as a scientific organization first and practical human-development/training system second. The canonical loop is:

Research → construct → operationalize → measure → evidence → finding → claim → intervention → training → experience/data → analysis → transfer → retention → replication/review → improved knowledge → improved training.

## Immediate priority
Do not jump to UI/product polish. Complete scientific infrastructure in this order:

1. Integration tests for the complete lifecycle.
2. Evidence resolution hardening, especially VERIFIED + UNCERTAIN semantics.
3. Knowledge-version lifecycle and revalidation.
4. Full provenance graph and downstream impact.
5. Training safety/adverse-event/stop-condition gates.
6. Participant/data governance.
7. Statistical execution + complete analysis audit coverage.
8. Bounded autonomous maintenance with authorized execution only.
9. Evidence-aware AI runtime.
10. Training OS execution/progression.
11. Human pilot infrastructure.
12. Closed-loop outcome → research → training updates.

## Current implementation additions
Recent commits on this branch include:
- b544a534 — scientific admission gates
- 83507d79 — training promotion routed through admission
- 3b57ce37 — intervention lifecycle gates
- f63d4e6e — admission/intervention APIs
- ecc2d427 — knowledge impact analysis
- dc29741b — knowledge impact APIs
- 57b91420 — knowledge review queue
- 464071dc — review queue API
- bf38c85d6 — knowledge freshness
- f69e0d85 — freshness persistence
- 34a7b55c — freshness APIs
- 67e0667a — dependency graph
- fa456658 — canonical Claude contract

## Important known risks
- Evidence resolution semantics must be reviewed for mixed VERIFIED/UNCERTAIN verdicts.
- Knowledge freshness currently flags review; it must not silently downgrade scientific state.
- Dependency graph is descriptive and must not be interpreted as causal efficacy.
- Autonomous maintenance must remain proposal-first and bounded.
- Some integration paths may still lack tests.
- Never report tests as passing unless actually executed.

## Working rule
Inspect → implement → test → fix → integrate → commit → continue.

Do not ask for small implementation choices unless a genuinely blocking scientific/product decision exists.
