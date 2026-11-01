# First Autonomous Research Run — Gap Analysis

## Purpose

Establish a verifiable end-to-end path for the first HDS literature review on self-discipline. This document records code-level observations, not a claim that the application has been executed or deployed.

## Confirmed in `completion/hds-v1`

- `app/scientific_retrieval.py` implements bounded PubMed and Crossref discovery and persists bibliographic metadata plus available abstracts as unverified source material.
- `app/research_engine.py` provides research workspaces, source ingestion, synthesis storage, review decisions, and provenance hashing.
- `app/research_agent.py` creates researcher tasks with explicit guardrails. It blocks a task if there are no retrieved sources or if no readable abstract/source text is available.
- `app/evidence_pipeline.py` checks that an evidence excerpt is present in parsed source text and prevents callers from directly marking evidence as verified.
- `docs/DEPLOYMENT.md` correctly states that a working CI build is not proof of deployment and that discovery results must remain unverified pending review.
- `POST /api/hds/research-loops/{run_id}/run-first-pass` now provides a bounded, authenticated orchestration step: start the loop if needed, retrieve literature, create/reuse the researcher task, execute the configured agent, and submit its output to the existing review gate. It returns explicit blocked/error states and never marks evidence verified.

## Integration gaps to verify

1. **Route/documentation alignment.** The documented bootstrap/start/retrieve/source routes are present in `app/main.py`; the new `run-first-pass` endpoint is the single-call entry point for the first bounded model pass.
2. **Model/provider execution.** The endpoint invokes `AgentExecutor`, which uses the configured provider and writes model-call and agent-run records. The default provider is deliberately a fail-closed placeholder. Runtime configuration and a successful live model call remain unverified.
3. **Readable source material.** Abstracts are persisted and passed into the researcher packet. If retrieved records have no readable text, the task remains blocked with a useful reason rather than fabricating evidence.
4. **Independent review.** The endpoint submits output to the existing output gate but does not approve it, verify evidence, promote findings, or publish conclusions. Human/independent review and evidence audits remain separate steps.
5. **Runtime/deployment.** Verify migrations, readiness, authenticated founder access, provider credentials and spend limits, and production isolation. Do not expose the service publicly before the trusted identity proxy and production secrets are configured.
6. **Automated coverage.** Confirm CI exercises the new endpoint's retrieval failure, missing abstract, provider failure, repeat-call behavior, and authorization paths.

## Acceptance criteria for the first run

- A workspace is created for the question: “Which interventions improve self-discipline, for whom, and under what conditions?”
- The authenticated founder can call `POST /api/hds/research-loops/{run_id}/run-first-pass` to run retrieval and one configured researcher-model pass, with persisted audit artifacts.
- Inclusion/exclusion criteria and the retrieval query are recorded before synthesis.
- Retrieval results include stable source identifiers, bibliographic metadata, URLs, and abstracts where available.
- Each candidate claim cites a source in the retrieved packet and an exact excerpt present in that source's stored text.
- Unsupported claims are omitted; observational findings are not described as causal.
- Contradictory evidence, study limitations, population/context limits, and uncertainty are reported explicitly.
- An independent review can reject the synthesis; only the approved workflow may advance its status.
- The run, errors, source records, model calls, and review decisions are auditable and reproducible.
- Automated tests cover provider errors, empty results, missing abstracts, duplicates, authorization isolation, invalid excerpts, and failed review gates.

## Current status

**Code change committed; runtime execution not yet verified.** CI is being checked for this change. The endpoint is on the development branch and is not proof of a deployed or configured service. No research conclusion should be labelled as produced by the running HDS system until an actual authenticated run and its persisted artifacts have been inspected.


## HDS research intelligence platform — next development direction

The intended product is not an AI literature summarizer. It is a governed research-development pipeline that turns scientific literature into traceable research opportunities and, where justified, testable intervention proposals for independent empirical evaluation.

### Product boundary

HDS AI may discover, organize, compare, summarize, generate hypotheses, draft protocols, and identify candidate collaborators. It must not autonomously declare novelty, establish scientific truth, approve human-subject research, recruit participants, run interventions, spend money, contact institutions, or publish findings. Those actions require qualified human authorization and, where relevant, independent ethics review.

### Required research objects

1. **Source record** — stable identifiers (DOI, PMID, URL), bibliographic metadata, provider, retrieval timestamp/query, access level, and verification status.
2. **Study record** — design, population, sample size, setting, measures, intervention/exposure, comparator, outcomes, follow-up, limitations, and risk-of-bias appraisal. Unknown fields stay explicitly unknown.
3. **Construct record** — definition, operationalizations, related constructs, competing definitions, measurement instruments, and provenance.
4. **Claim record** — atomic statement, claim type (definition/association/prediction/mechanism/causal effect), supporting and contradicting sources, exact excerpts, certainty, and reviewer decisions.
5. **Research gap** — the unresolved question, why existing evidence does not answer it, search coverage, counter-explanations, and confidence that the gap is genuine.
6. **Hypothesis** — falsifiable prediction, mechanism (or explicit unknown), population/context, measurable outcomes, and disconfirming observations.
7. **Intervention proposal** — target capability, theory of change, components, dose/progression, comparator, fidelity, safety/harms, feasibility, transfer, retention, and preregisterable outcomes.
8. **Research brief** — a human-readable package for an external researcher/institute, including methods, evidence map, uncertainty, novelty check, protocol outline, and open decisions.

### Required pipeline states

DISCOVERED → METADATA_VERIFIED → SCREENED → FULL_TEXT_REVIEWED → EXTRACTED → SYNTHESIZED → GAP_PROPOSED → HYPOTHESIS_DRAFTED → PROTOCOL_DRAFTED → INDEPENDENT_REVIEWED → READY_FOR_EXTERNAL_RESEARCH

These states are not automatic quality labels. Every transition must record actor, timestamp, rationale, evidence/provenance, and reviewer where required. No AI-generated state transition may bypass the human review gates for scientific approval or human-participant research.

### First research domain: mental capabilities

Start with a construct map, not a premature single theory of “mentality”. Candidate domains include self-regulation/executive function, emotion regulation, motivation, goal pursuit, learning/metacognition, stress/adaptation, social/interpersonal capability, judgment/decision-making, and self-beliefs/agency. For each, map definitions, boundaries, measures, populations, development across the lifespan, interventions, transfer, durability, and contradictory findings. Do not assume these constructs are interchangeable or that one general mental-toughness factor explains them all.

### First executable milestone

A bounded, reproducible literature-mapping run should:

- accept a research question and explicit scope;
- store exact database queries and retrieval timestamps;
- retrieve records from supported sources with stable identifiers;
- deduplicate records and preserve source provenance;
- distinguish metadata/abstract-only/full-text availability;
- screen records with recorded reasons and human override;
- extract structured study/construct data without inventing missing fields;
- attach each material claim to an exact source passage when full text is available;
- generate a synthesis with supporting, contradicting, and missing evidence;
- produce a research-gap register and candidate research briefs;
- export a complete audit bundle (machine-readable data plus human-readable report).

### Acceptance tests for scientific usefulness

- Same query/snapshot can be reproduced from stored search parameters and retrieval records.
- Duplicate publications and preprints/versions are linked without silently double-counting evidence.
- Abstract-only records cannot support claims about unobserved methods/results.
- Every extracted field is source-backed or marked unknown.
- Claims distinguish correlation, prediction, mechanism, and causal effects.
- Contradictory evidence is surfaced, not averaged away by fluent synthesis.
- Candidate novelty is labelled “potentially novel / requires expert and prior-art review”, never “new discovery” solely from AI search.
- Every intervention proposal includes safety, feasibility, comparator, fidelity, transfer, and follow-up considerations.
- Research briefs are exportable and independently reviewable without access to the HDS application.

### Immediate engineering priorities

1. Verify the existing end-to-end first-pass route and CI result on this branch.
2. Audit source verification, full-text acquisition/access controls, exact-quote provenance, and duplicate/version handling.
3. Confirm the research workspace stores queries, source states, screening decisions, extraction records, claims, and reviewer actions as linked entities.
4. Build construct/study extraction and evidence-map exports before adding more autonomous agents.
5. Add research-brief generation only after the underlying records are traceable and reviewable.
6. Keep external model use disabled until provider, privacy, data-processing, and spending decisions are explicitly approved.

**Status:** this section is a product and engineering specification. It is not evidence that these capabilities are implemented, operational, validated, or scientifically effective.


## Code audit — implementation boundary (2026-11-01)

This section records a static inspection of the development branch. It does not certify that the application has been run, that CI passed, or that a live search/model call succeeded.

### Verified in source code

- `app/scientific_retrieval.py` calls PubMed E-utilities and Crossref Works, stores bibliographic records and available abstracts, and labels the result `DISCOVERY_ONLY_UNVERIFIED`.
- Retrieval is bounded to at most 50 results per provider request. It deduplicates records within a retrieval run using a canonical identifier strategy and avoids duplicate workspace-source/retrieval-result inserts through database uniqueness constraints.
- The researcher task packet contains source metadata and readable abstract text, explicitly marks sources unverified, and blocks execution if no readable text is available.
- `app/agent_output_gate.py` stores agent output for review. Candidate excerpts can be materialized only as unverified evidence; verified evidence must be supplied through the separate review path.
- `app/evidence_pipeline.py` requires an excerpt to match text in a parsed source and prevents a caller from setting `verified=True` at attachment time. Verification is a separate reviewer action.
- The first-pass route performs one bounded retrieval/model pass and submits output to the output gate. Its response explicitly says that evidence verification, finding approval, and publication are not performed by this route.
- Provider configuration defaults to a fail-closed local placeholder. Ollama and Anthropic adapters exist, but the repository inspection does not establish that either is configured or reachable in a real deployment.
- The self-discipline protocol is explicitly labelled planned/not executed. The retrieval and first-pass tests stub provider responses and use a fake model provider; they validate control flow, not live scientific discovery or model quality.

### Confirmed limitations / not yet demonstrated

1. **No full-text acquisition pipeline was found in the inspected retrieval service.** PubMed abstracts and any Crossref abstract are discovery material. Full-text retrieval, lawful access checks, parsing, page/section coordinates, and version handling need a separate implementation or manual workflow.
2. **No systematic-review workflow is yet demonstrated.** The protocol describes screening and extraction, but code inspection has not established a complete dual-review screening system, structured study extraction, risk-of-bias appraisal, or a reproducible PRISMA-style flow.
3. **Search reproducibility is incomplete.** A retrieval run stores a query and selected provider(s), but the inspected implementation does not yet demonstrate per-provider query syntax/version, complete pagination, search-date metadata, saved search strategies, or exhaustive multi-database coverage.
4. **Novelty checking is not implemented as a validated capability.** A model can suggest a possible gap, but prior-art review and expert assessment remain necessary.
5. **Intervention design is not yet a validated generator.** HDS still needs structured intervention records with target construct, theory of change, dose, comparator, fidelity, safety, transfer, retention, and outcome measures.
6. **No live research execution was verified in this audit.** GitHub status checks for the inspected documentation commit returned no status entries, and the available first-pass tests are mocked. No conclusion about current CI success or deployment health is warranted.

### Priority order for the next implementation cycle

**P0 — prove a safe first run:** run the existing test suite and release gate in a controlled environment; test real PubMed/Crossref retrieval with a small bounded query; record provider errors and source identifiers; do not enable paid model execution by default.

**P1 — make literature mapping reproducible:** persist per-provider queries, timestamps, retrieval parameters, paging/limits, search logs, deduplication decisions, and source-version relationships. Add explicit screening decisions with reason codes and reviewer identity.

**P2 — build structured extraction:** create versioned study and construct schemas; store each field with source location and confidence/verification status; preserve unknowns rather than prompting the model to fill them.

**P3 — create evidence maps:** link atomic claims to exact excerpts, study design/population/outcomes, supporting and contradictory evidence, and reviewer assessments. Generate machine-readable exports and a human-readable report.

**P4 — develop candidate interventions:** only after the evidence map exists, generate protocol drafts with safety and evaluation plans. Require expert review and ethics approval before any human-participant study.

**Audit conclusion:** HDS has a meaningful research-workflow foundation and a guarded first-pass path in code. It is not yet an autonomous scientific discovery system, a validated systematic-review platform, or a proven intervention-development engine. The next engineering effort should strengthen reproducibility, full-text evidence handling, structured extraction, and reviewability before adding more agents.
