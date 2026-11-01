# HDS structured study extraction — v1

## Purpose
Create a conservative, auditable representation of study characteristics before HDS attempts synthesis or intervention design.

## Current implementation
`app/research_metadata.py` provides a versioned study-record schema and validation:
- nine predefined fields: design, population, sample size, setting, intervention/exposure, comparator, outcomes, follow-up, limitations;
- each field must be marked EXTRACTED, NOT_REPORTED, UNCLEAR, or REQUIRES_REVIEW;
- extracted values require a source locator;
- missing fields are explicitly stored as NOT_REPORTED and are never inferred;
- sample size must be a positive integer; outcomes must be a list;
- abstract-only extraction must identify abstract locations and cannot claim full-text provenance;
- records remain STRUCTURED_EXTRACTION_UNREVIEWED and require human review.

## Important limits
This is a schema/validation layer, not an AI extractor, full-text parser, systematic-review workflow, or risk-of-bias tool. Source locators are currently supplied by the caller; this module does not independently verify that a locator or quoted value exists in source text. That check must be implemented before scientific reliance.

## Next steps
1. Add a storage table and authenticated workspace-scoped API.
2. Verify every extracted value against exact source text and stable page/section/paragraph locators.
3. Add independent human review, correction history, and audit logs.
4. Add duplicate/version relationships between records.
5. Evaluate extraction accuracy against a manually annotated gold-standard set before enabling automated use.
