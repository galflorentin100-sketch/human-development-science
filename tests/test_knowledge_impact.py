import uuid
from app.database import Database
from app.models import now
from app.workflow import ResearchCycle

def test_impact_engine_proposes_review(tmp_path):
    from app.knowledge_impact_engine import KnowledgeImpactEngine
    db=Database(str(tmp_path/"i.db")); ResearchCycle(db)
    pid=ResearchCycle(db).run("impact")["project"]["id"]
    cid=str(uuid.uuid4()); tid=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(cid,pid,"claim","HYPOTHESIS","PRELIMINARY",0.1,"PROPOSED",now()))
    db.execute("INSERT INTO training_protocols(id,project_id,name,mechanism_hypothesis,challenge_domain,dosage,progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,version,created_at,source_claim_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,pid,"protocol","m","challenge","dose","progress","transfer","retention","safe","UNTESTED","DRAFT",1,now(),cid))
    out=KnowledgeImpactEngine(db).propagate(pid,"claims",cid)
    assert out["affected_count"]==1
    rows=KnowledgeImpactEngine(db).list(pid)
    assert rows[0]["affected_id"]==tid
