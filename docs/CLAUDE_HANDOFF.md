# Claude Handoff — HDS

> This document is an execution handoff, not a new product specification. Preserve the existing mission and architecture.

## Mission lock
HDS is a scientific organization first and a practical human-development/training system second. Its permanent loop is: research → evidence → findings → claims → interventions → training → measurement → transfer → retention → review → updated knowledge. Do not turn it into generic self-help or an unverified training-content platform.

## Current branch
`hds-scientific-provenance`

## Important existing modules
`scientific_admission.py`, `intervention_lifecycle.py`, `knowledge_impact.py`, `knowledge_graph.py`, `knowledge_review_queue.py`, `knowledge_freshness.py`, `autonomous_scientific_maintenance.py`, `autonomous_research.py`, `scientific_training_pipeline.py`, `outcome_feedback.py`, `finding_claim_bridge.py`, `scientific_completion.py`, `self_audit.py`, `lab_board.py`.


## Purpose
Continue the existing HDS project without changing its mission, architecture, scientific standards, or training-first direction.

## First instruction
Do not start by designing a new app. First inspect the repository and reconcile the actual implementation with `CLAUDE.md`.

## Execution protocol
For every continuation session:

1. Read `CLAUDE.md`.
2. Inspect the current branch and recent commits.
3. Run the existing test suite before changing code.
4. Inspect database initialization/migrations and import dependencies.
5. Select the highest-priority incomplete item from the roadmap below.
6. Implement a complete vertical slice, not a placeholder.
7. Add positive and negative tests.
8. Run the strongest available tests.
9. Fix failures caused by the change.
10. Commit with a precise message.
11. Update this handoff only when the actual project state changes.
12. Continue to the next coherent item if no real blocker exists.

## Priority roadmap

### P0 — Stabilize what already exists
- Verify all recent modules import correctly.
- Verify every referenced database table/column exists on a fresh database.
- Verify every new API route uses the correct existing auth/permission dependencies.
- Detect duplicate route definitions and incompatible assumptions.
- Run tests and fix regressions before adding features.

### P1 — Full scientific lifecycle integration
Build an integration test covering:

`evidence → independent review → accepted finding → proposed claim → verified claim → intervention → pilot training protocol → sessions → transfer/retention → analysis → finding feedback → review/update`

Also test failure paths:
- missing evidence
- unreviewed evidence
- conflicting evidence
- unsupported claim
- unsupported intervention
- training without transfer
- training without retention
- unauthorized promotion

### P2 — Conservative evidence resolution
Define and test the complete truth table:

- no reviews → `UNREVIEWED`
- only `UNCERTAIN` → `UNCERTAIN`
- only `VERIFIED` → `VERIFIED`
- `VERIFIED + UNCERTAIN` → conservative review-required state, never clean `VERIFIED`
- `VERIFIED + REJECTED` → `CONFLICTED`
- only `REJECTED` → `REJECTED`

Do not let a permissive resolver weaken claim or training gates.

### P3 — Knowledge version lifecycle
- Define admission rules for creating a knowledge version.
- Store evidence snapshots and dependency snapshots.
- Require rationale and authorized actor for updates.
- Preserve prior versions.
- Link revalidation and contradiction reviews to version history.
- Test stale and conflicting knowledge paths.

### P4 — Complete provenance graph
Represent and expose:

`evidence → finding → claim → intervention → training protocol → sessions → analysis → organizational decision`

The graph must distinguish factual support from mere linkage. Provenance must never be interpreted as efficacy.

### P5 — Safety and participant governance
Before real human pilots, implement:
- pre-session safety checks
- contraindication/stop-condition fields
- adverse-event recording
- escalation workflow
- protocol deviations
- consent and withdrawal handling
- participant pseudonymous references
- access/audit controls
- missing-data policy

### P6 — Analysis and audit completeness
- Ensure every analysis method records protocol hash, analysis-plan hash, dataset hash, method, population and timestamp.
- Add transfer and retention analyses.
- Keep descriptive and inferential conclusions separate.
- Do not add complex statistics without a concrete estimand and test requirement.

### P7 — Bounded autonomous maintenance
Connect:

`freshness/contradiction detection → deduplicated task proposal → authorized task execution → evidence review → human-controlled state transition`

The autonomous layer may propose and prepare work. It may not approve evidence or silently alter scientific truth.

### P8 — Scientific AI runtime
Require structured model outputs containing:
- statement
- classification
- evidence references
- uncertainty
- alternative explanations
- missing information
- recommended next test

Validate all model output through scientific governance before persistence.

### P9 — Training OS
Only after the preceding gates are tested:
- protocol versioning
- session planning
- progression rules
- adaptation logic
- safety overrides
- adherence and fatigue tracking
- transfer/retention measurement
- explainable recommendations with provenance

## Rules for Claude
- Never invent data or claim that tests passed without running them.
- Never convert hypotheses into facts.
- Never bypass permissions, approvals, cost controls, safety controls, idempotency, or audit logs.
- Never silently mutate or retire scientific knowledge.
- Prefer a smaller correct implementation over a broad speculative abstraction.
- If blocked, document the exact blocker and implement all non-blocked work first.

## Definition of done
A feature is complete only when code, schema, permissions, auditability, tests, documentation, and integration behavior agree.
