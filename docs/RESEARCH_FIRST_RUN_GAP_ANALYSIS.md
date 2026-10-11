# First Autonomous Research Run — Gap Analysis

## Purpose

Establish a verifiable end-to-end path for the first HDS literature review on self-discipline. This document records code-level observations, not a claim that the application has been executed or deployed.

## Confirmed in `completion/hds-v1`

- `app/scientific_retrieval.py` implements bounded PubMed and Crossref discovery and persists bibliographic metadata plus available abstracts as unverified source material.
- `app/research_engine.py` provides research workspaces, source ingestion, synthesis storage, review decisions, and provenance hashing.
- `app/research_agent.py` creates researcher tasks with explicit guardrails. It blocks a task if there are no retrieved sources or if no readable abstract/source text is available.
- `app/evidence_pipeline.py` checks that an evidence excerpt is present in parsed source text and prevents callers from directly marking evidence as verified.
- `docs/DEPLOYMENT.md` correctly states that a working CI build is not proof of deployment and that discovery results must remain unverified pending review.

## Integration gaps to verify

1. **Route/documentation mismatch.** The deployment runbook describes `/api/hds/research-loops/*` routes, while the inspected `app/main.py` exposes `/api/science/research-workspaces/*` routes. The exact route set must be confirmed from the complete target branch before using either sequence.
2. **Retrieval reachability.** `ScientificRetrievalService` exists, but its authenticated HTTP route was not found in the inspected portions of `app/main.py`. Confirm that a route instantiates it, checks project-scoped authorization, and returns persisted results without upgrading their verification status.
3. **Task execution.** Creating a research task is not equivalent to executing it. Verify the orchestrator can dispatch the task to an actual configured model provider and persist its output and model-call audit record.
4. **Readable source material.** Confirm abstracts are persisted and passed into the researcher packet. When no abstract is available, the workflow must fetch permitted readable text or remain blocked with a useful reason.
5. **Independent review.** Verify the researcher output is not promoted to a finding or verified evidence until source excerpts, evidence audits, and the required independent review gates pass.
6. **Runtime/deployment.** Verify tests, migrations, readiness, authenticated founder access, model-provider configuration, and production isolation. Do not expose the service publicly before the trusted identity proxy and production secrets are configured.

## Acceptance criteria for the first run

- A workspace is created for the question: “Which interventions improve self-discipline, for whom, and under what conditions?”
- Inclusion/exclusion criteria and the retrieval query are recorded before synthesis.
- Retrieval results include stable source identifiers, bibliographic metadata, URLs, and abstracts where available.
- Each candidate claim cites a source in the retrieved packet and an exact excerpt present in that source's stored text.
- Unsupported claims are omitted; observational findings are not described as causal.
- Contradictory evidence, study limitations, population/context limits, and uncertainty are reported explicitly.
- An independent review can reject the synthesis; only the approved workflow may advance its status.
- The run, errors, source records, model calls, and review decisions are auditable and reproducible.
- Automated tests cover provider errors, empty results, missing abstracts, duplicates, authorization isolation, invalid excerpts, and failed review gates.

## Current status

**Code inspection only — execution not yet verified.** This checklist must be completed against the exact branch intended for deployment. No research conclusion should be labelled as produced by the running HDS system until an actual run and its persisted artifacts have been inspected.
