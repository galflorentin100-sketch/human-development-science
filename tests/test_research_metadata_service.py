import pytest

from app.database import Database
from app.models import now
from app.research_metadata_service import StudyExtractionService
from app.workflow import ResearchCycle
from app.autonomous_research_loop import AutonomousResearchLoop


def _setup(tmp_path):
    db = Database(str(tmp_path / "study-extraction.db"))
    ResearchCycle(db)
    loop = AutonomousResearchLoop(db)
    run = loop.bootstrap_research("How can self-regulation be developed?")
    loop.start_research(run["run"]["id"])
    active = loop.get(run["run"]["id"])
    source_id = "source-study-1"
    db.execute(
        "INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",
        (source_id, "Study", "https://example.org/study-1", "Author", 2024, "PAPER", "", "unverified"),
    )
    text = "This randomized controlled trial included 120 adults. The intervention lasted eight weeks."
    import hashlib
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    db.execute(
        "INSERT INTO evidence_sources(id,source_id,state,content_hash,content,fetched_at,parsed_at,created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("parsed-1", source_id, "PARSED", digest, text, now(), now(), now()),
    )
    db.execute(
        "INSERT INTO research_workspace_sources(id,workspace_id,source_id,relevance,notes,content_hash,reviewed,created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("link-1", active["workspace_id"], source_id, "DISCOVERED", "{}", digest, 0, now()),
    )
    payload = {
        "study_design": {"value": "Randomized controlled trial", "status": "EXTRACTED",
                         "source_locator": "full_text:Methods", "source_excerpt": "randomized controlled trial"},
        "population": {"value": "120 adults", "status": "EXTRACTED",
                       "source_locator": "full_text:Participants", "source_excerpt": "120 adults"},
        "sample_size": {"value": 120, "status": "EXTRACTED",
                        "source_locator": "full_text:Participants", "source_excerpt": "120 adults"},
    }
    return db, active["workspace_id"], source_id, payload


def test_create_persists_unreviewed_provenance_and_idempotently_reuses(tmp_path):
    db, workspace_id, source_id, payload = _setup(tmp_path)
    service = StudyExtractionService(db)
    first = service.create(workspace_id, source_id, payload, "ai-extractor", "agent-1")
    second = service.create(workspace_id, source_id, payload, "ai-extractor", "agent-1")
    assert first["id"] == second["id"]
    assert first["status"] == "PENDING_REVIEW"
    assert first["extraction"]["scientific_status"] == "STRUCTURED_EXTRACTION_UNREVIEWED"
    assert first["extraction"]["fields"]["comparator"]["status"] == "NOT_REPORTED"


def test_create_blocks_excerpt_not_in_persisted_source(tmp_path):
    db, workspace_id, source_id, payload = _setup(tmp_path)
    payload["study_design"]["source_excerpt"] = "made up excerpt"
    with pytest.raises(ValueError, match="source_excerpt"):
        StudyExtractionService(db).create(workspace_id, source_id, payload, "ai", "agent")


def test_create_blocks_source_not_linked_to_workspace(tmp_path):
    db, workspace_id, source_id, payload = _setup(tmp_path)
    with pytest.raises(ValueError, match="not linked"):
        StudyExtractionService(db).create(workspace_id, "other-source", payload, "ai", "agent")


def test_review_requires_independent_reviewer_and_rationale(tmp_path):
    db, workspace_id, source_id, payload = _setup(tmp_path)
    service = StudyExtractionService(db)
    row = service.create(workspace_id, source_id, payload, "ai", "extractor")
    with pytest.raises(ValueError, match="independent"):
        service.review(row["id"], "extractor", "ACCEPTED", "looks good")
    with pytest.raises(ValueError, match="rationale"):
        service.review(row["id"], "reviewer", "ACCEPTED", "")
    accepted = service.review(row["id"], "reviewer", "ACCEPTED", "Compared each excerpt with the parsed source.")
    assert accepted["status"] == "ACCEPTED"
    assert accepted["reviewed_by"] == "reviewer"


def test_review_is_single_resolution(tmp_path):
    db, workspace_id, source_id, payload = _setup(tmp_path)
    service = StudyExtractionService(db)
    row = service.create(workspace_id, source_id, payload, "ai", "extractor")
    service.review(row["id"], "reviewer", "NEEDS_CORRECTION", "The sample description needs clarification.")
    with pytest.raises(ValueError, match="already been reviewed"):
        service.review(row["id"], "reviewer-2", "ACCEPTED", "re-review")
