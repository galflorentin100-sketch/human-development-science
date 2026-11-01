"""Structured, provenance-aware study metadata extraction for HDS.

This module validates extracted study descriptors. It does not assess risk of bias,
infer missing values, or certify scientific truth.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import json


STUDY_FIELDS = (
    "study_design",
    "population",
    "sample_size",
    "setting",
    "intervention_or_exposure",
    "comparator",
    "outcomes",
    "follow_up",
    "limitations",
)


class StudyRecordValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedField:
    value: Any
    status: str
    source_locator: str | None = None
    source_excerpt: str | None = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _field(raw: Any, name: str, source_text: str) -> ExtractedField:
    if raw is None:
        return ExtractedField(value=None, status="NOT_REPORTED", note="No value supplied; not inferred.")
    if not isinstance(raw, dict):
        raise StudyRecordValidationError(f"{name} must be an object with value/status/provenance")
    status = str(raw.get("status") or "").upper()
    if status not in {"EXTRACTED", "NOT_REPORTED", "UNCLEAR", "REQUIRES_REVIEW"}:
        raise StudyRecordValidationError(f"{name}: invalid extraction status")
    value = raw.get("value")
    locator = raw.get("source_locator")
    note = str(raw.get("note") or "")
    excerpt = raw.get("source_excerpt")
    if status == "NOT_REPORTED" and value is not None:
        raise StudyRecordValidationError(f"{name}: NOT_REPORTED fields cannot contain a value")
    if status == "EXTRACTED":
        if value is None or value == "" or value == []:
            raise StudyRecordValidationError(f"{name}: EXTRACTED fields require a value")
        if not isinstance(locator, str) or not locator.strip():
            raise StudyRecordValidationError(f"{name}: EXTRACTED fields require source_locator")
        if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in source_text:
            raise StudyRecordValidationError(f"{name}: source_excerpt must match the stored source text exactly")
    if status in {"UNCLEAR", "REQUIRES_REVIEW"} and not note:
        raise StudyRecordValidationError(f"{name}: {status} fields require an explanatory note")
    if name == "sample_size" and status == "EXTRACTED":
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise StudyRecordValidationError("sample_size must be a positive integer")
    if name == "outcomes" and status == "EXTRACTED" and not isinstance(value, list):
        raise StudyRecordValidationError("outcomes must be a list")
    return ExtractedField(value=value, status=status, source_locator=locator, source_excerpt=excerpt if status == "EXTRACTED" else None, note=note)


def validate_study_record(payload: dict, *, source_id: str, source_content_hash: str,
                          extractor: str, source_text: str, source_content_level: str = "FULL_TEXT") -> dict:
    """Return canonical JSON-ready study record with explicit unknowns and provenance."""
    if not isinstance(payload, dict):
        raise StudyRecordValidationError("study record must be an object")
    for name, value in (("source_id", source_id), ("source_content_hash", source_content_hash),
                        ("extractor", extractor)):
        if not isinstance(value, str) or not value.strip():
            raise StudyRecordValidationError(f"{name} is required")
    if not isinstance(source_text, str) or not source_text.strip():
        raise StudyRecordValidationError("source_text is required for excerpt verification")
    level = str(source_content_level).upper()
    if level not in {"ABSTRACT", "FULL_TEXT"}:
        raise StudyRecordValidationError("source_content_level must be ABSTRACT or FULL_TEXT")
    unknown = set(payload) - set(STUDY_FIELDS)
    if unknown:
        raise StudyRecordValidationError("unsupported study fields: " + ", ".join(sorted(unknown)))
    fields = {name: _field(payload.get(name), name, source_text).to_dict() for name in STUDY_FIELDS}
    if level == "ABSTRACT":
        for name, item in fields.items():
            if item["status"] == "EXTRACTED" and item["source_locator"] and not item["source_locator"].lower().startswith("abstract"):
                raise StudyRecordValidationError(
                    f"{name}: abstract-only records must use an abstract source locator"
                )
    return {
        "schema_version": "hds.study-record.v1",
        "source_id": source_id,
        "source_content_hash": source_content_hash,
        "source_content_level": level,
        "extractor": extractor,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "fields": fields,
        "scientific_status": "STRUCTURED_EXTRACTION_UNREVIEWED",
        "review_required": True,
    }


def serialize_study_record(record: dict) -> str:
    """Stable JSON serialization for storage/export."""
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
