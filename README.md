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
