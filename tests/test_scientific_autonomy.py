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

def test_claim_revision_requires_independent_approval(tmp_path):
    from app.claim_revision import ClaimRevisionService
    from app.models import now
    db=Database(str(tmp_path/"r.db")); ResearchCycle(db); pid=_setup(db)
    cid=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (cid,pid,"old","HYPOTHESIS","PRELIMINARY",0.2,"PROPOSED",now()))
    s=ClaimRevisionService(db)
    rev=s.propose(cid,"new","UNCERTAIN","new evidence","ev","system")
    assert s.approve(rev["id"],"reviewer")["statement"]=="new"

def test_contradiction_scan_flags_verified_vs_conflicted(tmp_path):
    from app.contradiction_engine import ContradictionEngine
    from app.evidence_pipeline import EvidencePipeline
    from app.models import now
    db=Database(str(tmp_path/"c.db")); ResearchCycle(db); pid=_setup(db)
    cid=str(uuid.uuid4()); a=str(uuid.uuid4()); b=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (cid,pid,"x","HYPOTHESIS","PRELIMINARY",0.1,"PROPOSED",now()))
    for sid in (a,b):
        db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",
                   (sid,sid,"https://example/"+sid,"PAPER","","test"))
    ep=EvidencePipeline(db)
    ep.ingest_text(a,"a"); ep.ingest_text(b,"b")
    ea=ep.attach(cid,a,"a"); eb=ep.attach(cid,b,"b")
    ep.review(ea["id"],"r1","VERIFIED","verified")
    ep.review(eb["id"],"r1","VERIFIED","verified")
    ep.review(eb["id"],"r2","CONFLICTED","conflict")
    result=ContradictionEngine(db).scan_claim(cid)
    assert len(result["contradictions"])==1

def test_autonomous_cycle_only_proposes_reviewable_work(tmp_path):
    from app.autonomous_research_cycle import AutonomousResearchCycle
    db=Database(str(tmp_path/"a.db")); ResearchCycle(db); pid=_setup(db)
    result=AutonomousResearchCycle(db).run(pid)
    assert result["requires_human_review"] is True
    assert result["proposed_research"][0]["status"]=="PROPOSED"
