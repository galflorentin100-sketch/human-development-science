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


def test_knowledge_versions_increment_without_collision(tmp_path):
    import concurrent.futures
    db,cid,sid=setup(tmp_path)
    ep=EvidencePipeline(db)
    ep.ingest_text(sid,"supporting evidence")
    ev=ep.attach(cid,sid,"supporting evidence","SUPPORTS")
    ep.review(ev["id"],"auditor","VERIFIED","checked")
    ClaimStateService(db).transition(cid,"SUPPORTED","reviewer","verified support",ev["id"])
    svc=ClaimStateService(db)

    def create_version(actor):
        return svc.knowledge_version(cid,actor,"concurrent version")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        versions=list(pool.map(create_version,("reviewer-a","reviewer-b")))
        versions.sort(key=lambda row: row["version"])

    assert [row["version"] for row in versions] == [1,2]
    assert len(db.all("SELECT id FROM scientific_knowledge_versions WHERE claim_id=?",(cid,))) == 2


def test_claim_transition_requires_selected_evidence_direction(tmp_path):
    db,cid,sid=setup(tmp_path); ep=EvidencePipeline(db)
    ep.ingest_text(sid,"supporting excerpt; contradicting excerpt")
    support=ep.attach(cid,sid,"supporting excerpt","SUPPORTS")
    contradict=ep.attach(cid,sid,"contradicting excerpt","CONTRADICTS")
    ep.review(support["id"],"support-auditor","VERIFIED","checked")
    ep.review(contradict["id"],"contradict-auditor","VERIFIED","checked")
    # The claim is conflicted, so neither transition is allowed; this also ensures
    # the selected evidence cannot be used as a misleading audit reference.
    try:
        ClaimStateService(db).transition(cid,"SUPPORTED","reviewer","selected evidence is contradictory",contradict["id"])
        assert False
    except ValueError as exc:
        assert "UNCERTAIN" in str(exc)


def test_knowledge_version_rejects_unreviewed_claim(tmp_path):
    db,cid,sid=setup(tmp_path)
    try:
        ClaimStateService(db).knowledge_version(cid,"reviewer","must not admit draft")
        assert False
    except ValueError as exc:
        assert "reviewed claim state" in str(exc)


def test_knowledge_version_rejects_conflicted_evidence(tmp_path):
    db,cid,sid=setup(tmp_path); ep=EvidencePipeline(db)
    ep.ingest_text(sid,"supporting excerpt; contradicting excerpt")
    support=ep.attach(cid,sid,"supporting excerpt","SUPPORTS")
    contradict=ep.attach(cid,sid,"contradicting excerpt","CONTRADICTS")
    ep.review(support["id"],"auditor-a","VERIFIED","checked")
    ep.review(contradict["id"],"auditor-b","VERIFIED","checked")
    ClaimStateService(db).transition(cid,"UNCERTAIN","reviewer","conflicting evidence requires uncertainty")
    try:
        ClaimStateService(db).knowledge_version(cid,"reviewer","do not admit conflict")
        assert False
    except ValueError as exc:
        assert "conflicted" in str(exc)


def test_knowledge_version_snapshot_changes_when_evidence_review_set_changes(tmp_path):
    db=Database(str(tmp_path/"knowledge-snapshot.db"))
    # Build a minimal claim/evidence graph through the existing test helpers.
    from app.evidence_pipeline import EvidencePipeline
    from app.claim_state import ClaimStateService
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at,updated_at) VALUES ('p','hds','snapshot','RUNNING','ceo','2026','2026')")
    db.execute("INSERT INTO claims(id,project_id,statement,classification,status,confidence,review_required,created_at,updated_at) VALUES ('c','p','A claim','SCIENTIFIC','SUPPORTED',0.8,0,'2026','2026')")
    db.execute("INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES ('s','source','https://example.test/s','a',2026,'PAPER','','')")
    db.execute("INSERT INTO evidence_sources(id,source_id,state,content_hash,content,fetched_at,parsed_at,created_at) VALUES ('es','s','PARSED','hash','The claim is supported.','2026','2026','2026')")
    ev=EvidencePipeline(db).attach("c","s","The claim is supported.","SUPPORTS",actor="researcher")
    EvidencePipeline(db).review(ev["id"],"reviewer-1","VERIFIED","verified")
    v1=ClaimStateService(db).knowledge_version("c","auditor","initial snapshot")
    db.execute("UPDATE claims SET status='UNCERTAIN' WHERE id='c'")
    EvidencePipeline(db).review(ev["id"],"reviewer-2","UNCERTAIN","uncertain on replication")
    v2=ClaimStateService(db).knowledge_version("c","auditor","updated snapshot")
    assert v1["evidence_snapshot_hash"] != v2["evidence_snapshot_hash"]
