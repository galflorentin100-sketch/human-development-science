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
