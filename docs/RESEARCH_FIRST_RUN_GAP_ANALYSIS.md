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
