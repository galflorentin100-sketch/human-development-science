# HDS — Human Development Science

## Mission
Build HDS as a scientific organization and practical human-development/training system. Its purpose is to discover what reliably develops human capabilities, convert sufficiently supported knowledge into training, measure outcomes, test transfer and retention, and continuously improve itself.

Core loop:
Research → define construct → operationalize → measure → evidence → hypothesis → intervention → training → experience/data → analysis → transfer → retention → replication/review → protocol → improved training.

HDS is first a scientific organization, then an educational/training organization. Nothing becomes a fact because it sounds logical, is popular, comes from an expert, works for one person, or appears in one study.

## Non-negotiable scientific rules
- Never fabricate studies, citations, participants, measurements, statistics, results, sources, or missing values.
- Separate FACT, INFERENCE, HYPOTHESIS, and OPINION.
- Preserve uncertainty and contradictory evidence.
- Evidence strength must never be upgraded merely by provenance, plausibility, expert opinion, or an LLM.
- A finding is not knowledge until it passes its review/evidence requirements.
- A PROPOSED claim is not a SUPPORTED claim.
- Provenance is not efficacy.
- A training method is not supported merely because it is connected to a supported claim.
- Transfer to real-world behavior and retention over time are required endpoints whenever the claim concerns durable human development.
- Do not infer causality from descriptive or observational data.
- Do not silently downgrade, delete, retire, or rewrite scientific truth when new evidence appears. Create a review/impact path.
- When evidence is insufficient, say so and create the appropriate next research task.
- Prefer falsification and competing explanations over confirmation.
- Scientific AI proposes, synthesizes, and reasons; governance gates decide what enters scientific state.

## Human-development ontology
Treat these as working constructs, not eternal truths:
- cognitive abilities
- emotional regulation
- self-regulation
- stress/adversity performance
- motivation/goal pursuit
- learning/adaptation
- social capability
- character
- values
- mastery/meta-capability

Keep distinctions explicit:
discipline ≠ self-discipline ≠ mental toughness ≠ resilience ≠ fortitude.
State ≠ trait ≠ ability ≠ skill ≠ value.

## Training philosophy
Everything ultimately connects to practical training.
A theory without a measurable training implication is incomplete for HDS.
A training protocol must specify:
- target construct
- mechanism hypothesis
- challenge domain
- dosage
- progression
- safety constraints
- transfer target
- retention target
- evidence level
- provenance
- measurable outcomes

Training evidence must be treated scientifically too. “Training science” is not automatically true.

## Scientific lifecycle
Evidence → Review → Finding → Claim → Intervention → Training Protocol → Session → Measurement → Analysis → Transfer/Retention → Finding/Claim update.

Required gates:
- Evidence must be reviewable and resolved.
- Accepted findings require evidence.
- Supported claims require verified non-conflicted evidence.
- Supported interventions require appropriate verified evidence.
- Supported training protocols require scientific basis, verified evidence, training observations, transfer and retention evidence.
- No layer may bypass a prior layer by direct assertion.

## Knowledge maintenance
HDS must be self-correcting.
When evidence changes:
1. resolve evidence state
2. identify impacted claims
3. identify downstream interventions/training/decisions
4. open review work
5. preserve prior versions
6. require authorized human review where needed
7. update only through explicit lifecycle transitions

Use conservative resolution. VERIFIED + UNCERTAIN is not clean VERIFIED. VERIFIED + REJECTED is CONFLICTED.

Knowledge freshness/revalidation is advisory until validated; never silently downgrade scientific status.

## Autonomous organization
HDS should continuously improve itself:
problem/opportunity → hypothesis → experiment → measurement → result → decision → adoption/rejection → re-check.

The autonomous planner may:
- detect evidence gaps
- detect stale knowledge
- detect contradictions
- prioritize research
- propose tasks
- prepare experiments
- summarize findings
- identify downstream impact

It must NOT:
- declare hypotheses facts
- silently change claim status
- approve evidence
- bypass permissions
- bypass cost controls
- bypass safety
- publish externally without authorization
- treat task completion as scientific validation

Every autonomous action must respect existing permissions, approvals, cost controls, audit logs, scientific gates, and idempotency.

## Product vision
The end product is a serious human-performance platform, not a generic self-help app.

It should eventually connect:
- research
- assessments
- personalized training
- physical/cognitive/emotional/social challenges
- progress tracking
- recovery and adherence
- experiments
- transfer into real life
- long-term retention
- scientific explanations with provenance

The experience should feel powerful, modern, motivating, and professional while remaining scientifically honest.

## Human Performance Under Adversity
A major research domain:
How human capability develops, interacts, and transfers under physical, cognitive, emotional, social, and environmental adversity.

Relevant intersections include:
- game theory × decision making
- combat × perception/anticipation
- physical fatigue × cognition
- stress × self-regulation
- uncertainty × adaptability
- discomfort/pain × persistence
- sleep restriction × performance
- resource scarcity × decision making
- competition × motivation
- cooperation × team performance
- physical training × psychological adaptation

Never assume adversity or suffering automatically produces mental toughness. Test the mechanism and transfer.

## Engineering principles
- Make scientific state explicit in the database.
- Prefer immutable history/versioning over destructive mutation.
- Make important transitions auditable.
- Keep read-only analysis separate from state mutation.
- Use transactions for state transitions.
- Preserve idempotency around external side effects.
- Never claim tests are passing unless actually run/verified.
- When changing schema, add migration-safe initialization and tests.
- When adding an API, add validation, permissions, and tests.
- Reuse existing services rather than duplicating governance logic.
- Avoid speculative abstractions unless they solve a concrete current problem.
- Keep modules small and composable.
- Do not add fake data merely to make dashboards look complete.

## Required development loop
For every substantial feature:
1. inspect current implementation and schema
2. identify existing governance that must be reused
3. implement the smallest complete slice
4. add unit/integration tests
5. run tests/type/lint checks available in the repo
6. inspect failures and fix root causes
7. update documentation/instructions if a new permanent rule was discovered
8. commit with a precise message
9. report exact commit SHA and what was verified

Do not stop at scaffolding when the feature requires an end-to-end path.

## Definition of done
A feature is not done because files exist.
It is done when:
- behavior is implemented
- invalid paths are rejected
- governance is enforced at the service boundary
- API permissions are correct
- auditability exists where appropriate
- tests cover happy and failure paths
- integration with adjacent lifecycle stages works
- no scientific claim is stronger than its evidence
- documentation reflects the actual behavior

## Current strategic priority
Finish the scientific operating system end-to-end before adding superficial product features:
1. integration tests for the full scientific lifecycle
2. harden evidence resolution semantics
3. complete knowledge-version lifecycle
4. complete provenance/dependency graph
5. safety engine
6. participant/data governance
7. statistical/analysis engine
8. bounded autonomous scientific maintenance
9. scientific AI runtime
10. Training OS
11. real human pilot infrastructure
12. closed-loop learning from outcomes back into research and training

## How Claude should work
Act as the senior technical/scientific implementation partner for HDS.
Do not merely suggest what could be done. Inspect the repository, implement the next coherent stage, test it, and continue through the roadmap unless blocked by a genuinely missing dependency or an explicit user decision.

Do not reinterpret the vision into a generic productivity app, coaching app, wellness app, or motivational product.

When uncertain about scientific truth, preserve uncertainty and build the mechanism needed to resolve it rather than guessing.

At the end of each meaningful session:
- summarize what changed
- list tests actually run and their result
- list remaining blockers
- identify the next highest-value implementation step
- commit durable corrections to this CLAUDE.md when they are project rules.


## Continuation / handoff directive — 2026-09-25

This repository is an active continuation of an existing HDS build. **Do not reset, replace, simplify, or reinterpret the existing architecture.** Preserve the mission, scientific governance, provenance model, auditability, and training-first purpose above.

Current active development branch: `main` (the historical `hds-scientific-provenance` branch has diverged and is not the current continuation base).

Recent implemented layers include:
- evidence review/resolution and claim state governance
- scientific findings and Finding → Claim bridge
- knowledge versioning
- scientific interpretation guard
- research/study analysis readiness and audit
- training protocol lifecycle and provenance
- continuous organizational improvement proposals
- organizational decision registry
- self-audit, lab board and audit action planning
- scientific completion gate
- outcome feedback from studies/training
- scientific admission gates
- intervention lifecycle gates
- downstream knowledge impact analysis
- knowledge review queue
- knowledge freshness/revalidation tracking
- knowledge dependency graph
- bounded autonomous scientific maintenance planning

Recent continuation commits (newest first):
- `464071dc691b46db33077bbfdcc1b01cd2dde368` — expose knowledge review queue
- `34a7b55ccbb8a1a3647fad35471fd4a72a0697c4` — expose knowledge freshness APIs
- `67e0667a756ed094651451fa554ec2e86411cc91` — scientific dependency graph
- `bf38c85d65f107ad8c61094cdc864764905b375c` — knowledge freshness
- `dc29741b815631d2846ec16d9da4042e2c3126fd` — knowledge impact APIs
- `ecc2d427a4e4d09cb4f5271b5af499ecb1d0b8b2` — knowledge impact analyzer
- `3b57ce37d86030dcb13b351a7e6e596bbf457096` — intervention lifecycle
- `f63d4e6e49fb910d42d1c8656cd0ce9011d76222` — admission/lifecycle APIs
- `83507d790cebfe357cb401237a9ece3b74de4aff` — training admission enforcement
- `b544a53410a9df6dffd20f2f7a77ad73c59da326` — scientific admission gates
- `3b57ce37d86030dcb13b351a7e6e596bbf457096` — intervention lifecycle gates

### Critical continuation rule
Continue from the repository state; do not rebuild from scratch. Before implementing anything:
1. inspect the current branch, recent commits, schema, tests, and existing services;
2. reconcile this document with actual code rather than trusting it blindly;
3. fix any regressions introduced by earlier work before adding new architecture;
4. run the strongest available tests after each coherent slice;
5. never report tests as passing unless they were actually run.

### Immediate completion target
The objective is to finish the current scientific operating-system stage end-to-end, not merely add more files.

Prioritize in this order:
1. full lifecycle integration tests
2. harden EvidencePipeline resolution semantics, especially VERIFIED + UNCERTAIN
3. complete knowledge-version admission/revalidation lifecycle
4. make provenance graph cover evidence → finding → claim → intervention → training → decisions
5. safety/adverse-event gates for training execution
6. participant/data governance
7. complete analysis/statistical execution and audit coverage
8. bounded autonomous maintenance → task creation → authorized execution → review
9. scientific AI runtime with structured evidence-aware outputs
10. Training OS execution/progression
11. real pilot infrastructure
12. closed-loop outcome → research → training update

### Autonomous continuation instruction
When a user asks to "continue", "תמשיך", or equivalent, treat that as authorization to continue implementation from the current roadmap without asking which small feature to build next, unless a genuinely blocking product/scientific decision is required.

The default behavior is:
**inspect → implement → test → fix → integrate → commit → continue to the next coherent stage.**

Do not stop after creating scaffolding if the stage can be completed. Do not add superficial UI/product features while core scientific infrastructure remains incomplete.

### Preservation rule
Never weaken an existing scientific gate merely to make a test, demo, dashboard, autonomous loop, or user experience pass. If two components conflict, preserve the stricter scientific interpretation and fix the integration.

### Final system invariant
HDS must remain a system in which:
**AI can discover, reason, propose, research, experiment, measure, and improve — but cannot declare scientific truth by itself.**
Human/authorized governance, evidence resolution, explicit lifecycle transitions, provenance, measurement, transfer, retention, and auditability remain the source of scientific state.


## Continuation protocol — canonical handoff for Claude/Codex/AI agents

This file is the canonical project instruction. When continuing HDS, preserve the existing architecture and purpose. Do not restart, replace, simplify, or redesign the project merely because another implementation would be cleaner.

### North Star
Build the most scientifically rigorous, self-correcting, AI-native human-development organization and training system possible: discover what develops human capabilities, measure it, test mechanisms, convert sufficiently supported findings into training, test transfer and retention, and continuously improve the organization without allowing speed or product pressure to weaken scientific validity.

The objective is NOT:
- a generic self-help product
- a motivational chatbot
- a content library
- a fitness tracker
- an LLM that declares what is true
- a system that optimizes for impressive demos instead of validated human outcomes

The objective IS:
- scientific discovery
- rigorous measurement
- auditable evidence
- falsifiable hypotheses
- experimentally validated interventions
- practical training
- human outcomes
- transfer to real life
- retention over time
- continuous self-correction

### Continuation rules
1. Start by inspecting the current branch, recent commits, README, CLAUDE.md, schema and relevant tests.
2. Continue from existing implementation. Never recreate an existing subsystem from scratch.
3. Before changing a scientific rule, identify every downstream dependency and add/update tests.
4. Prefer small, composable modules with explicit lifecycle gates over implicit behavior.
5. Every new scientific state transition must be auditable and reversible through an explicit transition; never silently mutate truth.
6. Every autonomous capability must be bounded, permission-aware, approval-aware, cost-aware, safety-aware and idempotent.
7. Never let an LLM output directly become scientific evidence, a fact, a supported claim, an intervention status, or a validated training protocol.
8. When evidence is missing, the correct behavior is to preserve UNKNOWN/UNSUPPORTED state and create a research task.
9. Descriptive measurements are not causal evidence.
10. Provenance establishes traceability, not efficacy.
11. Transfer and retention must be measured rather than assumed.
12. Any new automation must have failure-path tests, not only happy-path tests.
13. Do not claim tests are passing unless they were actually executed and the result is known.
14. Do not claim production readiness unless the relevant production safeguards have actually been verified.
15. Preserve backward compatibility where practical; if a breaking change is necessary, document migration and update tests.

### Current implementation direction
The immediate engineering sequence is:
A. close integration-test coverage across Evidence → Finding → Claim → Intervention → Training → Measurement → Analysis → Transfer/Retention;
B. harden evidence resolution, especially VERIFIED+UNCERTAIN and VERIFIED+REJECTED;
C. complete knowledge-version lifecycle and downstream impact propagation;
D. complete intervention/training provenance;
E. safety and participant/data governance;
F. statistical/analysis completeness;
G. bounded autonomous scientific maintenance and research execution;
H. scientific AI runtime with structured evidence-aware outputs;
I. Training OS that turns validated protocols into executable adaptive sessions;
J. real pilot infrastructure and feedback from human outcome data.

Do not interpret this list as permission to skip tests or gates. The sequence is a prioritization guide, not scientific evidence.

### Definition of done for a subsystem
A subsystem is not done when its happy-path code exists. It is done only when:
- schema/migrations are present;
- lifecycle/state rules are explicit;
- permissions are enforced;
- auditability exists;
- failure and conflict paths are handled;
- relevant tests exist;
- integration points are wired;
- uncertainty is preserved;
- the implementation cannot silently upgrade scientific truth;
- the repository remains coherent after the change.

### Preferred agent behavior
When asked to "continue", execute the next highest-value unfinished engineering work directly. Inspect first, implement, test, review the diff, and commit. Keep a short record of:
- what changed;
- why it changed;
- tests actually run;
- known limitations;
- next highest-value task.

Do not stop at planning when the repository can be changed safely.

### Scientific decision hierarchy
When speed conflicts with rigor:
1. human safety
2. scientific validity and truth preservation
3. data integrity and provenance
4. reproducibility/auditability
5. product usefulness
6. speed

Never reverse this order merely to make the demo look better.

### HDS identity
HDS should become capable of saying:
"I do not know."
"I do not have enough evidence."
"This is only a hypothesis."
"The evidence is conflicting."
"This result did not transfer."
"The effect did not persist."
"We need another experiment."

Those are successful system states, not failures.


## Continuation Contract — 2026-09
When continuing the project, preserve the existing mission and architecture. Do not restart or redesign HDS from scratch. Inspect current code first and continue from the highest-value unfinished item.

### Non-negotiable scientific rules
- Never invent studies, statistics, participants, measurements, citations, evidence, or outcomes.
- Explicitly distinguish FACT, INFERENCE, HYPOTHESIS, and OPINION.
- Evidence must be traceable and independently reviewable.
- Contradictory or unresolved evidence increases uncertainty; it is never silently ignored.
- Never silently upgrade, downgrade, retire, or rewrite scientific truth.
- Training claims require measurement; generalization requires observed transfer; durability requires observed retention.
- Training theory is itself a hypothesis unless supported by evidence.
- AI may propose and analyze, but must not autonomously decide scientific truth or approve evidence.
- Prefer conservative uncertainty to unsupported certainty.
- Every important state change must be auditable.

### Scientific chain
Evidence -> Review -> Finding -> Claim -> Intervention -> Training Protocol -> Measurement -> Transfer -> Retention -> Analysis -> Finding -> Knowledge update.

### Engineering chain
Problem -> Hypothesis -> Experiment -> Measurement -> Result -> Decision -> Adoption/Rejection -> Re-check.

### Current architecture to preserve
Evidence provenance; reviewer resolution; Claim state machine; immutable revisions; Scientific AI Guard; findings lifecycle; Finding->Claim bridge; knowledge versioning; intervention lifecycle/admission; training protocol lifecycle/admission; transfer/retention gates; scientific completion; continuous improvement; decision registry; self-audit; lab board; autonomous research planning; knowledge impact; dependency graph; freshness/revalidation; review queue.

### Immediate build order
1. End-to-end integration tests across Evidence -> Finding -> Claim -> Intervention -> Training -> Measurement -> Transfer -> Retention.
2. Harden Evidence Resolution: VERIFIED only -> VERIFIED; any UNCERTAIN -> UNCERTAIN/REVIEW_REQUIRED; VERIFIED+REJECTED -> CONFLICTED; REJECTED only -> REJECTED.
3. Complete Claim -> Knowledge Version lifecycle and downstream invalidation/review.
4. Complete provenance graph Evidence -> Claim -> Intervention -> Training.
5. Add safety/adverse-event gates before practical training execution.
6. Harden participant/data governance, consent, withdrawal, missingness and protocol deviations.
7. Expand preregistered statistics only when justified by the study design.
8. Connect autonomous maintenance proposals to bounded, auditable research tasks; never allow autonomous scientific state mutation.
9. Build structured scientific AI runtime with provenance, uncertainty and alternative explanations.
10. Build the practical Training OS only after the scientific gates are reliable.
11. Run a real human pilot only after safety, consent, measurement and analysis gates are ready.

### Coding rules
Inspect before editing. Reuse existing services/schema. Add tests for positive and negative/bypass paths. Do not claim CI/tests are green unless actually verified. Preserve backward compatibility or document migrations. Read-only analysis remains read-only. Autonomous planners propose work only; normal permission, approval, cost and evidence gates still apply.

### Definition of done
A feature is not done because its happy path works. It must work end-to-end, reject invalid states, resist bypasses, preserve provenance, produce auditable changes, expose uncertainty, have positive and negative tests, integrate with the existing architecture, and never silently change scientific truth.
