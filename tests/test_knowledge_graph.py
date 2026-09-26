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


def test_sync_materializes_only_resolvable_explicit_relationships(tmp_path):
    db=Database(str(tmp_path/"sync.db")); ResearchCycle(db); pid=_setup(db)
    source,claim,protocol=[str(uuid.uuid4()) for _ in range(3)]
    from app.models import now
    db.execute("INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(source,"s","https://example.org/s","","2026","PAPER","",""))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"c","FACT","PRELIMINARY",0.5,"PROPOSED",now()))
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_by,excerpt_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),claim,source,"SUPPORTS","x",0,"system","h",now()))
    from app.training import TrainingProtocolService
    p=TrainingProtocolService(db).create(pid,"p","m","d","dose","progress","transfer","retention","safe",source_claim_id=claim)
    result=KnowledgeDependencyGraph(db).sync_project(pid)
    graph=KnowledgeDependencyGraph(db).build(pid)
    assert len(graph["edges"]) >= 3
    graph=KnowledgeDependencyGraph(db).build(pid)
    assert any(e["relation"]=="GROUNDS" and e["from_id"]==claim for e in graph["edges"])


def test_sync_connects_experiment_and_result(tmp_path):
    db=Database(str(tmp_path/"experiment.db")); ResearchCycle(db); pid=_setup(db)
    from app.research import ResearchRepository
    h=ResearchRepository(db).hypothesis(pid,"Does training improve retention?")
    e=ResearchRepository(db).experiment(pid,h["id"],"pre-post")
    ResearchRepository(db).result(e["id"],"retention improved","descriptive result")
    result=KnowledgeDependencyGraph(db).sync_project(pid)
    graph=KnowledgeDependencyGraph(db).build(pid)
    assert any(x["relation"]=="TESTED_BY" and x["to_id"]==e["id"] for x in graph["edges"])
    assert any(x["relation"]=="HAS_RESULT" and x["from_id"]==e["id"] for x in graph["edges"])
    assert result["created_edges"] >= 2
