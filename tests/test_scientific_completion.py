from app.database import Database
from app.models import now
from app.scientific_completion import ScientificCompletionGate

def test_completion_gate_blocks_conflicted_knowledge_evidence(tmp_path):
    db=Database(str(tmp_path/"gate.db"))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at,updated_at) VALUES ('p','hds','x','RUNNING','ceo',?,?)",(now(),now()))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,status,confidence,review_required,created_at,updated_at) VALUES ('c','p','claim','SCIENTIFIC','SUPPORTED',0.9,0,?,?)",(now(),now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES ('s','s','https://example.test','PAPER','','')")
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,verified,created_by,excerpt,excerpt_hash,created_at) VALUES ('e','c','s','SUPPORTS',1,'r','excerpt','h',?)",(now(),))
    db.execute("INSERT INTO evidence_reviews(id,evidence_id,reviewer,verdict,rationale,created_at) VALUES ('r1','e','a','VERIFIED','ok',?)",(now(),))
    db.execute("INSERT INTO evidence_reviews(id,evidence_id,reviewer,verdict,rationale,created_at) VALUES ('r2','e','b','REJECTED','not ok',?)",(now(),))
    out=ScientificCompletionGate(db).evaluate("p")
    assert out["ready"] is False
    assert "conflicted_knowledge_evidence" in out["blockers"]

def test_completion_gate_blocks_stale_knowledge(tmp_path):
    db=Database(str(tmp_path/"stale.db"))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at,updated_at) VALUES ('p','hds','x','RUNNING','ceo',?,?)",(now(),now()))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,status,confidence,review_required,created_at,updated_at) VALUES ('c','p','claim','SCIENTIFIC','SUPPORTED',0.9,0,?,?)",(now(),now()))
    db.execute("INSERT INTO knowledge_freshness(id,entity_type,entity_id,review_interval_days,last_validated_at,next_review_at,status,owner,created_at,updated_at) VALUES ('k','CLAIM','c',30,?,?, 'REVIEW_REQUIRED','system',?,?)",(now(),"2000-01-01T00:00:00+00:00",now(),now()))
    out=ScientificCompletionGate(db).evaluate("p")
    assert out["ready"] is False
    assert "stale_knowledge_requires_review" in out["blockers"]
