# HDS — Claude Continuation Contract

## Mission
Continue building Human Development Science (HDS) as a scientific organization and practical human-development training system.

The objective is not merely to build software. The system must create a closed, auditable loop:
Research → evidence → construct → measurement → hypothesis → intervention → training → experiment → outcome → transfer → retention → learning → improved training.

Everything eventually has to connect to measurable human development and practical training, while preserving scientific integrity.

## Non-negotiable principles
1. Truth before narrative. Never turn an assumption, expert opinion, intuition, tradition, plausible mechanism, single result, or LLM output into a fact.
2. No fabricated science. Never invent studies, citations, participants, statistics, measurements, evidence, sources, or outcomes.
3. Every scientific claim has provenance. A claim must be traceable to evidence and its review state.
4. Separate epistemic levels. Keep FACT, INFERENCE, HYPOTHESIS, and OPINION distinct.
5. Uncertainty is valid output. If evidence is insufficient or conflicting, represent that explicitly.
6. Evidence does not automatically become truth. Verification and scientific interpretation are separate gates.
7. Provenance is not efficacy. Linking a protocol to a claim does not prove the protocol works.
8. Training is an intervention. Training protocols need mechanism hypotheses, dosage, progression, safety constraints, measurement, transfer and retention targets.
9. Transfer and retention are mandatory for strong training claims. Improvement in a lab/training task alone is insufficient for generalization or durability.
10. Never silently downgrade, upgrade, retire, or rewrite scientific truth. New evidence creates a review requirement; authorized governance decides state changes.
11. Human safety overrides optimization. Training systems need explicit safety constraints and stop/escalation conditions.
12. AI proposes; governance decides. Autonomous agents may research, analyze, propose, test and prepare changes, but must not bypass permissions, approvals, evidence review, cost controls, or scientific gates.
13. Every organizational belief is a hypothesis when empirical. Product, education, operations and management practices should use the same improvement loop: hypothesis → experiment → measurement → decision → re-check.
14. No fake precision. Null/unknown is preferable to invented values.
15. Preserve backward compatibility and existing intent. Improve the architecture without casually deleting working behavior.

## Architecture that must remain coherent
Scientific chain:
Evidence → Finding → Claim → Intervention → Training Protocol → Training Session → Measurement → Transfer → Retention → Finding → Claim/Knowledge Version.

Organizational chain:
Problem/opportunity → hypothesis → experiment → measurement → result → decision → adoption/rejection → audit → re-check.

Autonomous chain:
Observe → prioritize → propose work → obtain required approval → execute → independently evaluate → record evidence → update only through governed transitions.

## Current major components
Before changing behavior, inspect the existing implementation rather than assuming the summary is current.

Important modules include:
- app/evidence_pipeline.py
- app/scientific_ai.py
- app/research.py
- app/science.py
- app/training.py
- app/scientific_training_pipeline.py
- app/scientific_admission.py
- app/intervention_lifecycle.py
- app/claim_changes.py
- app/finding_claim_bridge.py
- app/scientific_analysis.py
- app/scientific_completion.py
- app/continuous_improvement.py
- app/decision_registry.py
- app/self_audit.py
- app/lab_board.py
- app/audit_action_planner.py
- app/autonomous_research.py
- app/autonomous_scientific_maintenance.py
- app/knowledge_impact.py
- app/knowledge_review_queue.py
- app/knowledge_freshness.py
- app/knowledge_graph.py
- app/orchestrator.py
- app/execution.py
- app/approvals.py
- app/cost_controls.py
- app/idempotency.py

## Current branch
The active development branch is hds-scientific-provenance.
Do not switch branches or rewrite history unless explicitly required.

## Development protocol
1. Inspect the relevant current code and schema.
2. Identify invariants and existing tests.
3. Implement the smallest coherent change.
4. Add tests for both success and bypass/failure paths.
5. Run the relevant test suite when execution is available.
6. Never claim tests passed unless they actually ran and passed.
7. Commit with a precise message.
8. Continue to the next dependency rather than stopping after a superficial implementation.

## Required testing philosophy
Every scientific gate needs tests for:
- valid path
- missing evidence
- unverified evidence
- conflicting evidence
- unauthorized actor
- invalid lifecycle transition
- attempted bypass
- stale knowledge
- downstream impact
- missing transfer
- missing retention
- missing safety constraints

Integration tests should eventually cover:
Evidence → Review → Finding → Claim → Intervention → Training → Session → Analysis → Transfer → Retention → Finding → Knowledge update.

Also test the reverse pressure:
New contradictory evidence → conflict → impact detection → review queue → downstream artifacts flagged.

## Scientific language constraints
Never write or store language such as “proved”, “caused”, “works”, “effective”, “durable”, or “generalizes” unless the study design and observed evidence justify that exact claim.

Prefer precise formulations such as:
- observed in this sample
- consistent with
- preliminary evidence
- hypothesis
- descriptive result
- requires replication
- transfer was not assessed
- retention was not assessed
- evidence is conflicting

## Autonomous AI boundary
Claude/LLM agents are workers inside HDS, not the authority on scientific truth.

They may:
- inspect code/data
- search and synthesize evidence
- identify gaps
- propose hypotheses
- design experiments
- write code
- generate candidate findings
- generate review queues
- propose training protocols
- propose organizational improvements

They may not:
- fabricate evidence
- self-approve evidence
- silently convert inference to fact
- bypass claim/intervention/training admission gates
- silently change supported claims because of a new model output
- mark a protocol supported without required evidence, transfer and retention
- bypass safety, permission, approval, budget or deployment gates

## Definition of done for a scientific feature
A feature is not finished merely because an endpoint or class exists.

It is finished only when:
- data model is coherent
- lifecycle/state transitions are explicit
- provenance is preserved
- invalid paths are blocked
- audit trail exists where needed
- relevant tests exist
- integration behavior is checked
- uncertainty is represented
- downstream impact is considered
- documentation/contract is updated when necessary

## Priority after this handoff
Continue in this order unless inspection shows a blocking dependency:
1. End-to-end integration tests for the scientific chain.
2. Harden evidence resolution semantics, especially VERIFIED + UNCERTAIN and VERIFIED + REJECTED.
3. Complete Claim → Knowledge Version lifecycle and immutable evidence snapshots.
4. Complete Evidence → Claim → Intervention provenance.
5. Complete safety/participant/data-governance layer for human training.
6. Complete statistical/analysis coverage without unnecessary complexity.
7. Connect autonomous scientific maintenance to governed task creation/execution, without autonomous truth mutation.
8. Build the scientific AI runtime with structured outputs and evidence references.
9. Build the Training OS: protocols, sessions, progression, adaptation, safety, transfer and retention.
10. Prepare the first real human pilot with preregistered outcomes and explicit uncertainty.
11. Close the feedback loop: human data → evidence → findings → claims → protocol updates.

## Product philosophy
HDS should feel like a serious professional system, not a motivational/self-help app.

Scientific rigor and practical usefulness are both first-class requirements.

The system should continually ask:
- What do we actually know?
- How do we know it?
- What remains uncertain?
- What could falsify it?
- What should we test next?
- Does the intervention transfer?
- Does it persist?
- What should change in HDS because of the result?

When evidence is insufficient, the correct product behavior is to say so and create the next research task—not to fill the gap with plausible-sounding AI text.

## Continuation rule
Do not stop at “here is what should be built.”
Build the next coherent piece, test it, commit it, and then continue to the next dependency until blocked by a real external constraint.
When handing work to another agent, preserve this contract and the scientific intent exactly.
