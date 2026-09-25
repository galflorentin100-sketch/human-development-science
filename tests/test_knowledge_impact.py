import uuid
from app.database import Database
from app.models import now

def test_impact_engine_proposes_review(tmp_path):
    from app.knowledge_impact_engine import KnowledgeImpactEngine
    db=Database(str(tmp_path/"i.db"))
    db.execute("CREATE TABLE claims(id TEXT PRIMARY KEY, project_id TEXT)")
    db.execute("CREATE TABLE training_protocols(id TEXT PRIMARY KEY, source_claim_id TEXT)")
    pid=str(uuid.uuid4()); cid=str(uuid.uuid4()); tid=str(uuid.uuid4())
    db.execute("INSERT INTO claims VALUES (?,?)",(cid,pid))
    db.execute("INSERT INTO training_protocols VALUES (?,?)",(tid,cid))
    out=KnowledgeImpactEngine(db).propagate(pid,"claims",cid)
    assert out["affected_count"]==1
    rows=KnowledgeImpactEngine(db).list(pid)
    assert rows[0]["affected_id"]==tid
