from app.database import Database
from app.workflow import ResearchCycle
from app.evidence_pipeline import EvidencePipeline
from app.claim_revision import ClaimRevisionService


def setup(tmp_path):
    db=Database(str(tmp_path/"revision.db"))
    out=ResearchCycle(db).run("claim revision test")
    return db,out["claims"][0]["id"],out["sources"][0]["id"]


def test_revision_approval_cannot_bypass_verified_evidence_gate(tmp_path):
    db,cid,sid=setup(tmp_path)
    service=ClaimRevisionService(db)
    revision=service.propose(cid,"A supported statement","SUPPORTED","requires verified evidence",(),actor="author")
    try:
        service.approve(revision["id"],"reviewer")
        assert False
    except ValueError as exc:
        assert "verified evidence" in str(exc)
    assert db.one("SELECT status FROM claims WHERE id=?",(cid,))["status"]=="REVIEW_REQUIRED"


def test_revision_approval_accepts_supported_claim_only_with_verified_support(tmp_path):
    db,cid,sid=setup(tmp_path)
    ep=EvidencePipeline(db)
    ep.ingest_text(sid,"seeded source content")
    ev=ep.attach(cid,sid,"seeded source content","SUPPORTS")
    ep.review(ev["id"],"auditor","VERIFIED","checked")
    service=ClaimRevisionService(db)
    revision=service.propose(cid,"A verified supported statement","SUPPORTED","verified evidence",(ev["id"],),actor="author")
    updated=service.approve(revision["id"],"reviewer")
    assert updated["status"]=="SUPPORTED"
    assert updated["statement"]=="A verified supported statement"
