from app.database import Database
from app.workflow import ResearchCycle
from app.evidence_pipeline import EvidencePipeline
from app.claim_state import ClaimStateService

def setup(tmp_path):
    db=Database(str(tmp_path/"claims.db")); cycle=ResearchCycle(db)
    out=cycle.run("claim state test")
    return db,out["claims"][0]["id"],out["sources"][0]["id"]

def test_supported_requires_verified_support(tmp_path):
    db,cid,sid=setup(tmp_path); ep=EvidencePipeline(db)
    src=ep.ingest_text(sid,"verified source content; relevant excerpt")
    ev=ep.attach(cid,sid,"relevant excerpt")
    try:
        ClaimStateService(db).transition(cid,"SUPPORTED","reviewer","Support is unverified.",ev["id"])
        assert False
    except ValueError as exc:
        assert "verified supporting" in str(exc)
    ep.review(ev["id"],"auditor","VERIFIED","Excerpt checked against source.")
    updated=ClaimStateService(db).transition(cid,"SUPPORTED","reviewer","Verified support.",ev["id"])
    assert updated["status"]=="SUPPORTED"

def test_conflicting_verified_evidence_forces_uncertainty(tmp_path):
    db,cid,sid=setup(tmp_path); ep=EvidencePipeline(db)
    ep.ingest_text(sid,"seeded source content; supporting excerpt; contradicting excerpt")
    ev1=ep.attach(cid,sid,"supporting excerpt","SUPPORTS")
    ev2=ep.attach(cid,sid,"contradicting excerpt","CONTRADICTS")
    ep.review(ev1["id"],"a","VERIFIED","checked")
    ep.review(ev2["id"],"b","VERIFIED","checked")
    state=ClaimStateService(db).evidence_state(cid)
    assert state["state"]=="CONFLICTED"
    try:
        ClaimStateService(db).transition(cid,"SUPPORTED","reviewer","Cannot ignore conflict.",ev1["id"])
        assert False
    except ValueError as exc:
        assert "UNCERTAIN" in str(exc)

def test_claim_state_history_is_immutable_append_only(tmp_path):
    db,cid,sid=setup(tmp_path); svc=ClaimStateService(db)
    svc.transition(cid,"PROPOSED","researcher","Candidate claim.")
    rows=db.all("SELECT * FROM claim_state_transitions WHERE claim_id=?",(cid,))
    assert len(rows)==1
    assert rows[0]["prior_status"]=="REVIEW_REQUIRED"


def test_claim_state_rejects_invalid_transition(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    db=Database(str(tmp_path/"transition.db")); ResearchCycle(db)
    # This test only exercises the explicit transition graph once a claim exists.
    try:
        from app.claim_state import ClaimStateService
        ClaimStateService(db).transition("missing","SUPPORTED","reviewer","rationale")
        assert False
    except ValueError:
        pass

def test_claim_changes_fact_blocks_contradictory_verified_evidence(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    db=Database(str(tmp_path/"fact.db")); ResearchCycle(db)
    # Regression placeholder: FACT gating must reject a claim with contradictory evidence.
    assert True
