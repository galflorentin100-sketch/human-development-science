import json
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


def test_accepted_synthesis_becomes_candidate_finding_not_claim(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    from app.research_engine import ResearchEngine
    db=Database(str(tmp_path/"finding.db")); ResearchCycle(db); pid=_setup(db)
    engine=ResearchEngine(db)
    ws=engine.create(pid,"What develops resilience?",owner="researcher")
    engine.activate(ws["id"],"researcher")
    source=EvidencePipeline(db).register_source("Paper","https://example.org/resilience","Author",2025)
    engine.add_source(ws["id"],source["id"])
    syn=engine.synthesize(ws["id"],"Candidate synthesis","limitations","uncertain","researcher")
    engine.review(syn["id"],"founder","ACCEPTED","reviewed")
    # Create a real, independently verified evidence reference before promotion.
    from app.evidence_pipeline import EvidencePipeline
    claim_id=str(uuid.uuid4())
    from app.models import now
    db.execute("INSERT INTO claims(id,project_id,statement,status,classification,confidence,review_required,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
               (claim_id,pid,"placeholder","SUPPORTED","INFERENCE",1.0,0,now(),now()))
    evidence=EvidencePipeline(db).attach(claim_id,source["id"],"Relevant excerpt","SUPPORTS",actor="researcher")
    EvidencePipeline(db).review(evidence["id"],"founder","VERIFIED","verified against source")
    # Rebuild the synthesis with the verified evidence reference.
    db.execute("UPDATE research_syntheses SET evidence_refs=? WHERE id=?",(json.dumps([evidence["id"]]),syn["id"]))
    finding=engine.promote_to_candidate_finding(syn["id"],"knowledge-manager")
    assert finding["status"]=="CANDIDATE"
    assert finding["classification"]=="INFERENCE"

def test_research_agent_task_is_governed(tmp_path):
    from app.research_engine import ResearchEngine
    from app.research_agent import ResearchAgentService
    from app.models import now
    db=Database(str(tmp_path/"agent.db")); ResearchCycle(db); pid=_setup(db)
    aid=str(uuid.uuid4())
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(aid,"researcher","researcher","research","[]","[\"READ\"]","1","ACTIVE",now()))
    ws=ResearchEngine(db).create(pid,"What develops resilience?",owner="founder")
    ResearchEngine(db).activate(ws["id"],"founder")
    result=ResearchAgentService(db).create_task(ws["id"],aid)
    assert result["task"]["project_id"]==pid
    assert result["task"]["assigned_agent_id"]==aid
    assert result["workspace_id"]==ws["id"]

def test_finding_promotion_requires_skeptic_review(tmp_path):
    import json
    from app.evidence_pipeline import EvidencePipeline
    from app.research_engine import ResearchEngine
    from app.skeptic import SkepticService
    db=Database(str(tmp_path/"gate.db")); ResearchCycle(db); pid=_setup(db)
    engine=ResearchEngine(db)
    ws=engine.create(pid,"Does friction affect adherence?",owner="researcher"); engine.activate(ws["id"],"researcher")
    source=EvidencePipeline(db).register_source("Paper","https://example.org/friction","Author",2025)
    engine.add_source(ws["id"],source["id"])
    syn=engine.synthesize(ws["id"],"candidate","limitations","uncertain","researcher")
    # An accepted synthesis alone is not enough.
    engine.review(syn["id"],"founder","ACCEPTED","reviewed")
    try:
        engine.promote_to_candidate_finding(syn["id"],"knowledge-manager")
        assert False
    except ValueError as exc:
        assert "skeptic_review" in str(exc)
    skeptic=SkepticService(db).create(ws["id"],syn["id"],"skeptic-agent")
    SkepticService(db).record(skeptic["id"],["possible alternative explanation"],["missing comparison"],["selection effects"])
    SkepticService(db).review(skeptic["id"],"ACCEPTED","founder","objections addressed")
    try:
        engine.promote_to_candidate_finding(syn["id"],"knowledge-manager")
        assert False
    except ValueError as exc:
        assert "evidence_audit" in str(exc)
