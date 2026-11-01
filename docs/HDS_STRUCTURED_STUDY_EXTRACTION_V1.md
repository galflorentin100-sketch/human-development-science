# HDS structured study extraction — v1

## Purpose
Create a conservative, auditable representation of study characteristics before HDS attempts synthesis or intervention design.

## Implemented
- `app/research_metadata.py`: versioned nine-field study schema.
- Each field is marked EXTRACTED, NOT_REPORTED, UNCLEAR, or REQUIRES_REVIEW.
- Every extracted value requires a source locator and a verbatim excerpt that matches the stored source text exactly.
- Missing values are explicitly NOT_REPORTED; no inference fills gaps.
- Sample size must be a positive integer; outcomes must be a list.
- Abstract-only records must use abstract locators.
- `app/research_metadata_service.py`: workspace-scoped persistence pinned to the parsed-source content hash, idempotent for the same workspace/source/version, and independent review.
- New records remain PENDING_REVIEW. A reviewer other than the extractor must record ACCEPTED, REJECTED, or NEEDS_CORRECTION with a rationale.
- Authenticated API routes are exposed for create, list, and review. Each route checks project-level authorization.

## API
- POST `/api/hds/research-workspaces/{workspace_id}/study-extractions`
- GET `/api/hds/research-workspaces/{workspace_id}/study-extractions`
- POST `/api/hds/study-extractions/{extraction_id}/review`

Creation body: `source_id`, `fields`, optional `extractor`, optional `source_content_level`.
Review body: `decision`, `rationale`.

## Limits
Exact excerpt matching proves only that the excerpt exists in stored text; it does not prove the extracted interpretation is correct. Source locators are caller-supplied and not independently parsed/verified against page coordinates. Full-text/abstract classification is also supplied by the caller and should be bound to acquisition metadata in a later version. This is not a risk-of-bias assessment or an automated systematic-review workflow.
