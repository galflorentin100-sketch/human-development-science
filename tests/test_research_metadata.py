import pytest

from app.research_metadata import (
    STUDY_FIELDS,
    StudyRecordValidationError,
    serialize_study_record,
    validate_study_record,
)


def _base():
    return {
        "study_design": {
            "value": "Randomized controlled trial",
            "status": "EXTRACTED",
            "source_locator": "full_text:Methods:Study design",
            "source_excerpt": "Randomized controlled trial",
        },
        "sample_size": {
            "value": 120,
            "status": "EXTRACTED",
            "source_locator": "full_text:Methods:Participants",
            "source_excerpt": "120 participants",
        },
        "population": None,
    }


def test_missing_fields_are_explicit_not_inferred():
    record = validate_study_record(
        _base(), source_id="source-1", source_content_hash="sha256:abc",
        extractor="human-reviewer", source_text="Randomized controlled trial with 120 participants.", source_content_level="FULL_TEXT",
    )
    assert set(record["fields"]) == set(STUDY_FIELDS)
    assert record["fields"]["comparator"]["status"] == "NOT_REPORTED"
    assert record["fields"]["comparator"]["value"] is None
    assert record["review_required"] is True
    assert record["scientific_status"] == "STRUCTURED_EXTRACTION_UNREVIEWED"


def test_extracted_value_requires_source_locator():
    payload = _base()
    payload["population"] = {"value": "Adults", "status": "EXTRACTED"}
    with pytest.raises(StudyRecordValidationError, match="source_locator"):
        validate_study_record(payload, source_id="s", source_content_hash="h", extractor="ai", source_text="Randomized controlled trial with 120 participants.")


def test_not_reported_cannot_contain_guessed_value():
    payload = _base()
    payload["population"] = {"value": "Adults", "status": "NOT_REPORTED"}
    with pytest.raises(StudyRecordValidationError, match="cannot contain a value"):
        validate_study_record(payload, source_id="s", source_content_hash="h", extractor="ai", source_text="Randomized controlled trial with 120 participants.")


def test_sample_size_must_be_positive_integer():
    payload = _base()
    payload["sample_size"]["value"] = "about 100"
    with pytest.raises(StudyRecordValidationError, match="positive integer"):
        validate_study_record(payload, source_id="s", source_content_hash="h", extractor="ai")


def test_abstract_only_cannot_claim_full_text_locator():
    payload = _base()
    with pytest.raises(StudyRecordValidationError, match="abstract source locator"):
        validate_study_record(payload, source_id="s", source_content_hash="h", extractor="ai", source_text="Randomized controlled trial with 120 participants.",
                              source_content_level="ABSTRACT")


def test_unclear_requires_note_and_unknown_fields_are_rejected():
    payload = _base()
    payload["population"] = {"value": None, "status": "UNCLEAR"}
    with pytest.raises(StudyRecordValidationError, match="explanatory note"):
        validate_study_record(payload, source_id="s", source_content_hash="h", extractor="ai")
    payload["unexpected"] = {"value": "x", "status": "EXTRACTED", "source_locator": "p.1"}
    with pytest.raises(StudyRecordValidationError, match="unsupported study fields"):
        validate_study_record(payload, source_id="s", source_content_hash="h", extractor="ai")


def test_serialization_is_stable():
    record = validate_study_record(_base(), source_id="s", source_content_hash="h", extractor="ai", source_text="Randomized controlled trial with 120 participants.")
    assert serialize_study_record(record) == serialize_study_record(record)


def test_extracted_excerpt_must_exist_verbatim_in_source():
    payload = _base()
    payload["study_design"]["source_excerpt"] = "randomized trial (not in source)"
    with pytest.raises(StudyRecordValidationError, match="match the stored source text exactly"):
        validate_study_record(payload, source_id="s", source_content_hash="h", extractor="ai", source_text="Randomized controlled trial with 120 participants.")
