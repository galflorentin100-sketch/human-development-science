# Human Development Science — Company OS

An auditable foundation for an AI-native Human Development Science company.

## Current state
Reconstructed core Company OS: persistent company state, 17-agent registry, permissions, bounded research workflow, evidence/claim records, founder intelligence and a dashboard.

## Run
```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Scientific rule
Do not fabricate evidence or data. Separate established findings, preliminary evidence, hypotheses, assumptions and unknowns. Experimental functionality must be validated before being treated as established.

## Not production-ready
Production PostgreSQL, authentication hardening, live source ingestion, external model providers, background workers, sandboxed tool execution and deployment hardening remain future work.


## Operating loop
Founder goals are orchestrated into projects and tasks. Tasks execute through permission checks, model-call audit logging, evaluation, failure capture, lessons, replanning, and decision gates. High-risk or low-confidence decisions can create pending human approvals.

## Truth policy
Unverified model output is never treated as scientific evidence. Evidence must be traceable; claims and findings should preserve uncertainty and review status. The current local provider is intentionally a safe placeholder and does not provide external scientific retrieval.
