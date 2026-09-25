from app.database import Database
from app.workflow import ResearchCycle
from app.knowledge_graph import KnowledgeDependencyGraph
import uuid

def _setup(db):
    from app.models import now
    c,a,p=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(c,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(a,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(p,c,"o","ACTIVE",a,now()))
    return p

def test_explicit_edges_are_idempotent_and_traceable(tmp_path):
    db=Database(str(tmp_path/"graph.db")); ResearchCycle(db); pid=_setup(db)
    g=KnowledgeDependencyGraph(db)
    g.add_edge(pid,"EVIDENCE","e1","SUPPORTS","CLAIM","c1",["source:1"],"reviewer")
    g.add_edge(pid,"EVIDENCE","e1","SUPPORTS","CLAIM","c1",["source:1"],"reviewer")
    trace=g.trace(pid,"EVIDENCE","e1")
    assert trace["node_count"]==2
    assert any(n["type"]=="CLAIM" and n["id"]=="c1" for n in trace["nodes"])

def test_impact_trace_does_not_claim_efficacy(tmp_path):
    db=Database(str(tmp_path/"impact.db")); ResearchCycle(db); pid=_setup(db)
    g=KnowledgeDependencyGraph(db)
    g.add_edge(pid,"CLAIM","c1","INFORMS","INTERVENTION","i1")
    g.add_edge(pid,"INTERVENTION","i1","IMPLEMENTED_BY","TRAINING_PROTOCOL","p1")
    result=g.impacted(pid,"CLAIM","c1")
    assert result["node_count"]==2
    assert "causal" in result["policy"] or "efficacy" in result["policy"]
