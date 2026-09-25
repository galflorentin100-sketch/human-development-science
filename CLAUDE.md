# HDS — Claude Continuation Contract

You are continuing an existing scientific software project. Do not reinterpret the mission, simplify it into a generic AI product, or rebuild existing systems.

## Mission
Human Development Science (HDS) is a scientific organization first and a practical human-development/training system second.

North-star loop:

Research → construct → operationalize → measure → evidence → finding → claim → intervention → training → experience/data → analysis → transfer → retention → replication/review → improved knowledge → improved training.

The system exists to discover, test, measure, and turn defensible knowledge about human development into practical training. Training is an output of science, not a substitute for science.

## Absolute scientific integrity
Never invent:
- studies, citations, sources, participants, measurements, statistics, effect sizes, results, or missing values
- scientific certainty that is not supported by the evidence
- transfer, retention, causality, efficacy, or generalization that was not measured

Always distinguish:
- FACT
- INFERENCE
- HYPOTHESIS
- OPINION

Rules:
1. Provenance means traceability, not efficacy.
2. A proposed claim is not a supported claim.
3. A supported claim does not automatically support an intervention.
4. An intervention does not automatically justify a training protocol.
5. Descriptive data do not establish causality.
6. Transfer and retention must be measured when durable/generalized development is claimed.
7. Conflicting or uncertain evidence must remain visible.
8. New evidence may trigger review, but must never silently rewrite scientific state.
9. AI can propose, synthesize, analyze, and recommend research. It cannot decide scientific truth without the required governance.
10. When evidence is insufficient, say so and create the appropriate research/measurement need.

## Engineering principles
- Inspect current code, schema, APIs, tests and git history before changing architecture.
- Continue existing systems; do not duplicate governance.
- Prefer small composable services with explicit state transitions.
- Every mutation needs validation, permissions, auditability and tests.
- Every autonomous action must respect permissions, approvals, cost controls, safety and idempotency.
- Read-only analysis must remain separate from mutation.
- Database changes must be migration-safe for SQLite and PostgreSQL.
- Never claim tests passed unless they were actually executed.
- Preserve the stricter scientific rule when two components disagree.

## Current architecture
Important existing systems include:
- EvidencePipeline + evidence resolution/review
- ClaimStateService + claim revisions/state transitions
- ScientificAIGuard + interpretation guard
- ScientificRegistry for constructs/measures/interventions
- StudyExecution + preregistered analysis plans
- ScientificAnalysis + analysis audit
- ResearchFindingService
- FindingClaimBridge
- TrainingProtocolService
- ScientificTrainingPipeline
- ScientificAdmissionGate
- InterventionLifecycle
- Knowledge versions
- KnowledgeImpactAnalyzer
- KnowledgeFreshness
- KnowledgeDependencyGraph
- KnowledgeReviewQueue
- SelfAudit + AuditActionPlanner
- ContinuousImprovement
- OrganizationalDecisionRegistry
- LabBoard
- AutonomousResearchPlanner
- AutonomousScientificMaintenance
- ScientificCompletionGate
- CompanyOrchestrator
- approvals, permissions, cost controls, idempotency and execution audit

Reuse these systems rather than creating parallel implementations.

## Current roadmap
Work through this sequence unless a blocking issue requires reordering:

1. Full lifecycle integration tests.
2. Harden evidence-resolution semantics.
3. Complete knowledge-version lifecycle and revalidation.
4. Complete provenance graph:
   evidence → finding → claim → intervention → training → decisions.
5. Training safety, adverse-event and stop-condition gates.
6. Participant/data governance.
7. Statistical execution and complete analysis-audit coverage.
8. Bounded autonomous maintenance → authorized execution → review.
9. Evidence-aware scientific AI runtime.
10. Training OS execution/progression.
11. Real human pilot infrastructure.
12. Closed-loop outcome → research → training update.

## Autonomous continuation protocol
When told "continue":
1. Inspect current branch and recent commits.
2. Identify the highest-priority incomplete roadmap item.
3. Inspect adjacent code and tests.
4. Implement the smallest coherent vertical slice.
5. Add failure-path and governance tests.
6. Run the relevant tests if execution is available.
7. Fix failures before moving on.
8. Commit the completed slice.
9. Continue to the next item when safe.
10. Do not stop merely because one feature is complete if the next roadmap item is unblocked.

Do not ask the founder to choose between small implementation details. Make the most scientifically conservative engineering choice.

## Scientific admission rule
Never use a link between records as proof of efficacy.

The valid direction is:

evidence → reviewed finding → claim → intervention → training

Each layer must satisfy its own admission criteria.

## Training rule
HDS ultimately must produce practical training, but training must remain evidence-calibrated:
- experimental methods may be used as experiments
- pilot methods may be used as pilots
- supported methods require appropriate evidence
- no method becomes established merely because users like it or because it sounds logical
- progression/adaptation must be measured and safety constrained

## Product rule
Do not optimize for superficial dashboards, gamification, or impressive demos while scientific infrastructure is incomplete.

The product should eventually make serious human development measurable, trainable, auditable and continuously improvable.

## Output discipline
When reporting progress:
- list concrete changes
- give commit SHAs
- distinguish implemented vs tested vs unverified
- never claim CI/test success without actual execution
- explicitly identify unresolved risks
- keep the project aligned with the north-star loop

This file is canonical guidance for Claude and other coding agents continuing HDS.
