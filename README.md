# Human Development Science — Company OS

An auditable foundation for an AI-native Human Development Science company.

## Current state
HDS is an auditable Company OS foundation with persistent company state, a 17-agent registry, project-scoped permissions, bounded autonomous research, evidence/claim/knowledge workflows, founder intelligence, a unified Founder OS dashboard, approvals, failure/recovery controls, and scientific provenance.

## Run
```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the unified Founder OS dashboard.

## Scientific rule
Do not fabricate evidence or data. Separate established findings, preliminary evidence, hypotheses, assumptions and unknowns. Experimental functionality must be validated before being treated as established.

## Production status
The repository now includes PostgreSQL support, production identity-signing enforcement, governed code-change proposals with approval/verification/rollback, HDS safety governance, production Docker/Compose definitions, and CI container/Compose validation. A real deployment still requires an operator-managed IdP/proxy, secrets, observability, backups, and an isolated code-execution runner for autonomous patch application.


## Operating loop
Founder goals are orchestrated into projects and tasks. Tasks execute through permission checks, model-call audit logging, evaluation, failure capture, lessons, replanning, and decision gates. High-risk or low-confidence decisions can create pending human approvals.

## Truth policy
Unverified model output is never treated as scientific evidence. Evidence must be traceable; claims and findings should preserve uncertainty and review status. The current local provider is intentionally a safe placeholder and does not provide external scientific retrieval.
