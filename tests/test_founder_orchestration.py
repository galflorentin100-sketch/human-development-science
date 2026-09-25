from app.database import Database
from app.workflow import ResearchCycle
import uuid

def _setup(db):
    from app.models import now
    c,a,p=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(c,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(a,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(p,c,"o","ACTIVE",a,now()))
    return p

def test_founder_snapshot_surfaces_attention(tmp_path):
    from app.founder_intelligence import FounderIntelligence
    db=Database(str(tmp_path/"f.db")); ResearchCycle(db); pid=_setup(db)
    snap=FounderIntelligence(db).snapshot(pid)
    assert "scientific_health" in snap
    assert "requires_founder_attention" in snap

def test_agent_registry_has_scientific_roles():
    from app.agent_registry import AgentRegistry
    roles={x["id"] for x in AgentRegistry().list()}
    assert {"researcher","skeptic","evidence_auditor","experiment_designer","analyst"} <= roles
