import uuid

from app.database import Database
from app.workflow import ResearchCycle

def _setup(db):
    from app.models import now
    c,a,p=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(c,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(a,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(p,c,"o","ACTIVE",a,now()))
    return p

def test_approved_queue_starts_research_workspace(tmp_path):
    from app.research_queue import ResearchQueue
    from app.research_engine import ResearchEngine
    db=Database(str(tmp_path/"research.db")); ResearchCycle(db); pid=_setup(db)
    q=ResearchQueue(db)
    row=q.propose(pid,"What changes transfer?","evidence gap","EVIDENCE_GAP",priority="HIGH")
    q.approve(row["id"],"founder")
    started=q.begin(row["id"],"founder")
    assert started["queue_item"]["status"]=="IN_PROGRESS"
    assert started["workspace"]["status"]=="ACTIVE"
    assert started["workspace"]["question"]=="What changes transfer?"

def test_research_synthesis_requires_sources_and_review(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    from app.research_engine import ResearchEngine
    db=Database(str(tmp_path/"synthesis.db")); ResearchCycle(db); pid=_setup(db)
    engine=ResearchEngine(db)
    ws=engine.create(pid,"Does challenge affect transfer?",owner="researcher")
    engine.activate(ws["id"],"researcher")
    try:
        engine.synthesize(ws["id"],"candidate synthesis")
        assert False, "synthesis without sources must fail"
    except ValueError as exc:
        assert "at least one source" in str(exc)
    source=EvidencePipeline(db).register_source("Paper","https://example.org/paper","Author",2025)
    engine.add_source(ws["id"],source["id"],"RELEVANT","primary study")
    syn=engine.synthesize(ws["id"],"candidate synthesis","small sample","causal effect not established","researcher")
    assert syn["status"]=="CANDIDATE"
    accepted=engine.review(syn["id"],"founder","ACCEPTED","reviewed source scope and limitations")
    assert accepted["status"]=="ACCEPTED"
    assert engine.get(ws["id"])["status"]=="REVIEWED"
