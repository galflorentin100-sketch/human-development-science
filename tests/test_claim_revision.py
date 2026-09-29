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


def test_descriptive_finding_cannot_be_promoted_to_causal_claim(tmp_path):
    import json
    from uuid import uuid4
    from app.models import now
    from app.finding_claim_bridge import FindingClaimBridge
    db,cid,sid=setup(tmp_path)
    eid=str(uuid4()); fid=str(uuid4())
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_by,excerpt_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(eid,cid,sid,"SUPPORTS","observed excerpt",1,"system","hash-causal",now()))
    db.execute("INSERT INTO evidence_reviews(id,evidence_id,reviewer,verdict,rationale,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),eid,"auditor","VERIFIED","checked",now()))
    db.execute("INSERT INTO research_findings(id,project_id,source_type,source_id,statement,classification,status,evidence_refs,interpretation,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (fid,db.one("SELECT project_id FROM claims WHERE id=?",(cid,))["project_id"],"EVIDENCE",eid,"The intervention causes improvement","DESCRIPTIVE","ACCEPTED",json.dumps([eid]),"descriptive only","reviewer",now()))
    try:
        FindingClaimBridge(db).propose_claim(fid,"reviewer")
        assert False
    except ValueError as exc:
        assert "causal claim" in str(exc)


def test_supported_causal_claim_requires_explicit_causal_basis(tmp_path):
    db,cid,sid=setup(tmp_path)
    ep=EvidencePipeline(db)
    ep.ingest_text(sid,"seeded source content")
    ev=ep.attach(cid,sid,"seeded source content","SUPPORTS")
    ep.review(ev["id"],"auditor","VERIFIED","checked")
    service=ClaimRevisionService(db)
    try:
        service.propose(cid,"The intervention causes improvement","SUPPORTED","causal claim",(ev["id"],),actor="author")
        assert False
    except ValueError as exc:
        assert "causal basis" in str(exc)

def test_supported_causal_claim_records_explicit_basis(tmp_path):
    db,cid,sid=setup(tmp_path)
    ep=EvidencePipeline(db)
    ep.ingest_text(sid,"seeded source content")
    ev=ep.attach(cid,sid,"seeded source content","SUPPORTS")
    ep.review(ev["id"],"auditor","VERIFIED","checked")
    service=ClaimRevisionService(db)
    revision=service.propose(cid,"The intervention causes improvement","SUPPORTED","causal claim",(ev["id"],),actor="author",causal_basis="Randomized controlled evidence supports a causal interpretation",causal_basis_type="RANDOMIZED_TRIAL")
    updated=service.approve(revision["id"],"reviewer")
    assert updated["status"]=="SUPPORTED"
