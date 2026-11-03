# HDS Developer Agent — Version 1.0 backlog

The local agent selects one small task per cycle. Complete tasks only when tests
or documented manual verification support the claim.

## Priority 0 — prove the local development loop
- [ ] HDS-DEV-001: Inspect repository structure and write an evidence-based report of the highest-risk gaps in the local research MVP.
- [ ] HDS-DEV-002: Add focused tests for the local research launcher and scheduler, including shutdown and failure handling.
- [ ] HDS-DEV-003: Test scheduler persistence and error-handling edge cases without changing scientific governance.

## Priority 1 — research MVP reliability
- [ ] HDS-DEV-010: Audit research first-pass API error states and provenance preservation; add tests.
- [ ] HDS-DEV-011: Test evidence-map serialization for empty, partial, verified and unverified data.
- [ ] HDS-DEV-012: Test dashboard loading, refresh failures and empty states.
- [ ] HDS-DEV-013: Improve Windows operating documentation, setup, backups and troubleshooting.

## Priority 2 — version 1.0 readiness
- [ ] HDS-DEV-020: Add a reproducible local smoke-test command using existing dependencies and safe fixtures.
- [ ] HDS-DEV-021: Audit local security defaults and document risks; never weaken safety gates.
- [ ] HDS-DEV-022: Create a version 1.0 acceptance checklist mapping capabilities to tests/manual verification.
- [ ] HDS-DEV-023: Review scientific documentation for overstated validation claims and preserve uncertainty.

Generated code is not proof of completion. Research outputs remain unverified
until independent scientific review. The agent must never approve or publish findings.
