import pytest
from uuid import uuid4
from app.database import Database
from app.workflow import ResearchCycle
from app.knowledge_freshness import KnowledgeFreshness
from app.evidence_pipeline import EvidencePipeline


def setup(tmp_path):
    db = Database(str(tmp_path / "freshness.db"))
    project = ResearchCycle(db).run("knowledge freshness gate")["project"]
    return db, project["id"]


def insert_claim(db, project_id, status):
    claim_id = str(uuid4())
    db.execute(
        "INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (claim_id, project_id, "A reviewed scientific statement.", "INFERENCE", "VERIFIED", 0.8, status, "2026-01-01T00:00:00Z"),
    )
    return claim_id


def test_freshness_rejects_unaccepted_claim_as_active_knowledge(tmp_path):
    db, project_id = setup(tmp_path)
    claim_id = insert_claim(db, project_id, "PROPOSED")
    with pytest.raises(ValueError, match="SUPPORTED claims"):
        KnowledgeFreshness(db).register("CLAIM", claim_id, project_id=project_id)


def test_freshness_allows_supported_claim(tmp_path):
    db, project_id = setup(tmp_path)
    claim_id = insert_claim(db, project_id, "SUPPORTED")
    ep = EvidencePipeline(db)
    source = ep.register_source("source", "https://example.org/freshness-" + claim_id)
    ep.ingest_text(source["id"], "verified excerpt")
    evidence = ep.attach(claim_id, source["id"], "verified excerpt", "SUPPORTS")
    ep.review(evidence["id"], "auditor", "VERIFIED", "checked")
    row = KnowledgeFreshness(db).register("CLAIM", claim_id, project_id=project_id)
    assert row["status"] == "ACTIVE"


def test_freshness_cannot_revalidate_claim_after_downgrade(tmp_path):
    db, project_id = setup(tmp_path)
    claim_id = insert_claim(db, project_id, "SUPPORTED")
    ep = EvidencePipeline(db)
    source = ep.register_source("source", "https://example.org/downgrade-" + claim_id)
    ep.ingest_text(source["id"], "verified excerpt")
    evidence = ep.attach(claim_id, source["id"], "verified excerpt", "SUPPORTS")
    ep.review(evidence["id"], "auditor", "VERIFIED", "checked")
    freshness = KnowledgeFreshness(db)
    row = freshness.register("CLAIM", claim_id, project_id=project_id)
    db.execute("UPDATE claims SET status='UNCERTAIN' WHERE id=?", (claim_id,))
    with pytest.raises(ValueError, match="SUPPORTED claims"):
        freshness.validate("CLAIM", claim_id, "reviewer", "revalidate", project_id=project_id)
    assert db.one(
        "SELECT status FROM knowledge_freshness WHERE id=?", (row["id"],)
    )["status"] == "ACTIVE"
