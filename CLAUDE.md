# HDS — Human Development Science

## Mission — do not change this
Build HDS as a **scientific organization first, and a practical human-development/training system second**.

HDS exists to discover, test, measure, and continuously improve methods for developing human capabilities. Scientific knowledge must ultimately become measurable training; training must generate data; data must feed back into research.

Core loop:

Research → construct → operationalize → measure → evidence → finding → claim → intervention → training protocol → session → measurement → transfer → retention → analysis → replication/review → updated knowledge → improved training.

**Do not turn HDS into generic self-help, motivational content, a chatbot, or a collection of untested training wisdom.**

## Non-negotiable truth policy

1. Never fabricate studies, citations, sources, participants, measurements, statistics, results, or missing values.
2. Explicitly distinguish:
   - FACT
   - INFERENCE
   - HYPOTHESIS
   - OPINION
3. Preserve uncertainty and contradictory evidence.
4. Provenance is not evidence of efficacy.
5. Plausibility is not evidence.
6. Expert opinion is not automatically fact.
7. One study is not automatically established knowledge.
8. A PROPOSED claim is not a SUPPORTED claim.
9. Descriptive/observational evidence must not be converted into causal language.
10. Never silently upgrade scientific certainty.
11. Never silently delete, retire, downgrade, or rewrite scientific knowledge because new evidence appears.
12. New contradictory evidence creates a review/impact path.
13. Scientific AI may propose, synthesize, compare, and identify gaps; governance determines scientific state.
14. When evidence is insufficient, explicitly say so and create the next appropriate research action.

## Human-development ontology

Treat these as working constructs, not eternal truths:

- cognitive capability
- emotional regulation
- self-regulation
- stress/adversity performance
- motivation/goal pursuit
- learning/adaptation
- social capability
- character
- values
- mastery/meta-capability

Maintain explicit distinctions:

discipline ≠ self-discipline ≠ mental toughness ≠ resilience ≠ fortitude

state ≠ trait ≠ ability ≠ skill ≠ value

Do not treat this taxonomy as scientifically final. It is itself revisable.

## Training principle

Everything ultimately connects to training.

A theoretical finding without a measurable practical implication is incomplete for HDS.

A training protocol must specify:

- target construct
- mechanism hypothesis
- challenge domain
- dosage
- progression rule
- safety constraints
- transfer target
- retention target
- evidence level
- provenance
- measurable outcomes

Training methods themselves require evidence. “Training science” is not automatically true.

## Scientific lifecycle and gates

Required direction:

Evidence → Review → Finding → Claim → Intervention → Training → Measurement → Transfer/Retention → Knowledge update.

Do not bypass layers.

### Evidence
Evidence must be traceable and reviewable.

Resolution policy must be conservative:

- VERIFIED only → VERIFIED
- UNCERTAIN → UNCERTAIN
- VERIFIED + UNCERTAIN → UNCERTAIN / review required
- VERIFIED + REJECTED → CONFLICTED
- REJECTED only → REJECTED

### Finding
A finding cannot become accepted knowledge without the required evidence.

### Claim
A proposed claim is not scientific support.

SUPPORTED requires verified, non-conflicted support.

### Intervention
EXPERIMENTAL → PILOT → SUPPORTED → RETIRED.

SUPPORTED interventions require appropriate verified evidence. The existence of a supported claim does not itself prove intervention efficacy.

### Training
DRAFT → PILOT → SUPPORTED → RETIRED.

A SUPPORTED training protocol requires, at minimum, explicit scientific basis, verified/non-conflicted evidence, training observations, transfer evidence, retention evidence, and safety constraints.

Provenance links never substitute for efficacy evidence.

## Knowledge maintenance

HDS must be self-correcting.

When knowledge changes:

1. resolve evidence
2. identify impacted claims
3. identify downstream interventions
4. identify downstream training protocols
5. identify organizational decisions
6. preserve prior versions
7. create review work
8. require appropriate human authorization
9. update only through explicit lifecycle transitions

Knowledge freshness is a **review signal**, not an automatic scientific downgrade.

The dependency graph and impact analyzer are advisory. They must never silently mutate scientific truth.

## Autonomous organization

HDS should improve itself continuously:

problem/opportunity → hypothesis → experiment → measurement → result → decision → adoption/rejection → re-check.

The autonomous system MAY:

- detect evidence gaps
- detect stale knowledge
- detect contradictions
- prioritize research
- propose tasks
- prepare experiments
- summarize evidence
- map downstream impact
- create bounded review work

It MUST NOT:

- declare hypotheses facts
- approve evidence
- silently change claim status
- bypass permissions
- bypass approvals
- bypass cost controls
- bypass safety constraints
- publish externally without authorization
- treat task completion as scientific validation
- invent missing data

Every autonomous action must remain bounded, auditable, idempotent, and reversible where possible.

## Current autonomous architecture

Important modules:

- `app/autonomous_research.py` — read-only work prioritization
- `app/autonomous_scientific_maintenance.py` — bounded maintenance proposals
- `app/knowledge_freshness.py` — revalidation tracking
- `app/knowledge_impact.py` — downstream impact analysis
- `app/knowledge_graph.py` — dependency graph
- `app/knowledge_review_queue.py` — review proposals
- `app/scientific_admission.py` — layer admission gates
- `app/intervention_lifecycle.py` — intervention lifecycle
- `app/scientific_training_pipeline.py` — training provenance/readiness
- `app/outcome_feedback.py` — study/training outcome → candidate finding
- `app/finding_claim_bridge.py` — accepted finding → proposed claim
- `app/scientific_completion.py` — project scientific completion gate
- `app/self_audit.py` — scientific/organizational audit
- `app/lab_board.py` — founder/lab aggregation

## Product architecture

HDS should ultimately have these layers:

1. Scientific knowledge system
2. Research execution system
3. Measurement/assessment system
4. Training protocol engine
5. Human/session data system
6. AI scientific reasoning layer
7. Autonomous organization layer
8. Founder/lab command center

The AI layer must sit **inside** governance, never above it.

## Current branch

Continue development from:

`hds-scientific-provenance`

Repository:

`galflorentin100-sketch/human-development-science`

Do not reset, rewrite, or replace the existing architecture merely to make implementation easier.

Before changing an existing subsystem:

1. inspect current implementation
2. inspect its tests
3. preserve existing gates
4. make the smallest coherent change
5. add regression tests
6. verify integration
7. document architectural changes

## Current important commits

Recent scientific-governance work includes:

- `b544a53410a9df6dffd20f2f7a77ad73c59da326` — scientific admission gates
- `83507d790cebfe357cb401237a9ece3b74de4aff` — training promotion uses admission gates
- `3b57ce37d86030dcb13b351a7e6e596bbf457096` — intervention lifecycle gates
- `f63d4e6e49fb910d42d1c8656cd0ce9011d76222` — admission/intervention APIs
- `ecc2d427a4e4d09cb4f5271b5af499ecb1d0b8b2` — knowledge impact analysis
- `dc29741b815631d2846ec16d9da4042e2c3126fd` — impact APIs
- `57b91420c0b994356d959747df2affe589b2bd0b` — knowledge review queue
- `464071dc691b46db33077bbfdcc1b01cd2dde368` — review queue API
- `bf38c85d65f107ad8c61094cdc864764905b375c` — knowledge freshness
- `f69e0d8566bd3158cef09ebff9b92eff9f802275` — freshness persistence
- `34a7b55ccbb8a1a3647fad35471fd4a72a0697c4` — freshness APIs
- `67e0667a756ed094651451fa554ec2e86411cc91` — knowledge dependency graph

These are context, not a substitute for inspecting current code.

## Immediate engineering priority

Do NOT jump straight into UI polish.

Finish the scientific operating system in this order:

1. end-to-end integration tests
2. evidence-resolution hardening
3. knowledge-version lifecycle
4. complete provenance graph
5. safety engine
6. participant/data governance
7. statistical analysis expansion
8. autonomous research execution
9. scientific AI runtime
10. training protocol/session engine
11. controlled human pilot
12. feedback loop from real outcomes into research

## Definition of “done”

A feature is not done because the code exists.

For scientific functionality, “done” means:

- schema exists
- service exists
- API exists where appropriate
- permission/approval behavior is enforced
- audit trail exists
- regression tests exist
- integration path is tested
- failure states are explicit
- uncertainty is preserved
- provenance is traceable
- no scientific status can be silently upgraded

For a scientific intervention/training method, “done” additionally requires appropriate measurement, transfer, retention, safety, and evidence lifecycle.

## Coding rules

- Prefer explicit validation over implicit assumptions.
- Fail closed on missing scientific evidence.
- Do not use LLM output as evidence unless it is explicitly sourced and independently reviewed.
- Never fabricate a fallback number.
- Use null/unknown where data is missing.
- Keep deterministic governance separate from probabilistic AI generation.
- Every state-changing autonomous operation must be auditable.
- Every external side effect needs the existing permission/approval/idempotency/cost controls.
- Keep changes modular.
- Add tests for both positive and negative paths.
- Do not claim tests are passing unless they were actually run or verified through CI.

## Final product north star

HDS should become a continuously learning scientific organization that can:

**discover → test → measure → train → observe → challenge itself → update → train better.**

The system should become more capable without becoming less scientifically honest.


## Claude continuation contract — preserve the project exactly

When Claude continues HDS, it should behave as the continuation of the existing engineering/scientific team, not as a new project.

### First action on every substantial session
1. Read this file completely.
2. Inspect git status and recent commits.
3. Inspect the relevant implementation AND its tests before editing.
4. Never reset, reinitialize, replace, or simplify the architecture merely for convenience.
5. Continue from the current branch and preserve all existing scientific gates.

### Execution style
Claude should work continuously through the highest-priority unfinished item rather than stopping after creating a skeleton. For each item:
- implement the smallest coherent production-quality change;
- add positive and negative regression tests;
- integrate it with existing governance;
- verify it;
- commit it with a precise message;
- then continue to the next unfinished dependency.

Do not declare a feature complete merely because files or endpoints exist.

### Scientific invariant
At every layer, preserve this invariant:

`new information -> provenance -> review -> explicit state transition -> downstream impact review -> measurable validation`

No LLM output, expert assertion, plausible mechanism, or provenance link may silently become scientific truth.

### Priority rule
If the user says "continue", "תמשיך", or asks Claude to continue the project, Claude should use the current Immediate engineering priority and keep progressing in order until a real blocker is reached. Do not repeatedly ask what to build next when the repository already defines the next priority.

### Handoff rule
If a task is too large for one context window:
- finish the current coherent unit;
- commit it;
- leave the repository in a runnable state;
- update this file only when architecture or priorities materially change;
- continue from the next explicit item on the next session.

### Current objective
The immediate objective is to finish the scientific operating system before UI/product polish:
1. integration tests
2. evidence-resolution hardening
3. knowledge-version lifecycle
4. complete provenance graph
5. safety engine
6. participant/data governance
7. statistical expansion
8. autonomous research execution
9. scientific AI runtime
10. training protocol/session engine
11. controlled human pilot
12. real-outcome feedback loop

After each milestone, re-run the self-audit and inspect whether any new scientific bypass exists.

### Never optimize for appearance of progress
Prefer a smaller verified feature over many unverified files. Never claim CI/tests are green unless actually verified.
