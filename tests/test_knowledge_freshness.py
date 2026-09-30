import pytest
from app.database import Database
from app.workflow import ResearchCycle
from app.knowledge_freshness import KnowledgeFreshness
from app.evidence_pipeline import EvidencePipeline
from app.claim_state import ClaimStateService


def setup(tmp_path):
    db = Database(str(tmp_path / "freshness.db"))
    out = ResearchCycle(db).run("knowledge freshness gate")
    return db, out["claims"][0]["id"], out["sources"][0]["id"], out["project"]["id"]


def test_freshness_rejects_unaccepted_claim_as_active_knowledge(tmp_path):
    db, claim_id, _, project_id = setup(tmp_path)
    with pytest.raises(ValueError, match="SUPPORTED claims"):
        KnowledgeFreshness(db).register("CLAIM", claim_id, project_id=project_id)


def test_freshness_allows_supported_claim(tmp_path):
    db, claim_id, source_id, project_id = setup(tmp_path)
    evidence = EvidencePipeline(db).attach(claim_id, source_id, "seeded excerpt", "SUPPORTS")
    EvidencePipeline(db).review(evidence["id"], "auditor", "VERIFIED", "checked")
    ClaimStateService(db).transition(
        claim_id, "SUPPORTED", "reviewer", "verified support", evidence["id"]
    )
    row = KnowledgeFreshness(db).register("CLAIM", claim_id, project_id=project_id)
    assert row["status"] == "ACTIVE"


def test_freshness_cannot_revalidate_claim_after_downgrade(tmp_path):
    db, claim_id, source_id, project_id = setup(tmp_path)
    evidence = EvidencePipeline(db).attach(claim_id, source_id, "seeded excerpt", "SUPPORTS")
    EvidencePipeline(db).review(evidence["id"], "auditor", "VERIFIED", "checked")
    ClaimStateService(db).transition(
        claim_id, "SUPPORTED", "reviewer", "verified support", evidence["id"]
    )
    freshness = KnowledgeFreshness(db)
    row = freshness.register("CLAIM", claim_id, project_id=project_id)
    ClaimStateService(db).transition(
        claim_id, "UNCERTAIN", "reviewer", "new uncertainty requires review"
    )
    with pytest.raises(ValueError, match="SUPPORTED claims"):
        freshness.validate("CLAIM", claim_id, "reviewer", "revalidate", project_id=project_id)
    assert db.one(
        "SELECT status FROM knowledge_freshness WHERE id=?", (row["id"],)
    )["status"] == "ACTIVE"
