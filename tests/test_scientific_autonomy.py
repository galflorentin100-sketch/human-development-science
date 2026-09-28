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
    rev=s.propose(cid,"new","UNCERTAIN","new evidence",None,"system")
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

def test_maintenance_task_has_stable_identity_link(tmp_path):
    from app.autonomous_scientific_maintenance import AutonomousScientificMaintenance
    db=Database(str(tmp_path/"maintenance.db")); ResearchCycle(db); pid=_setup(db)
    service=AutonomousScientificMaintenance(db)
    proposal={"kind":"REVALIDATION","entity_type":"CLAIM","entity_id":str(uuid.uuid4()),
              "title":"Revalidate claim X","reason":"review interval elapsed"}
    service.propose=lambda project_id=None: {"count":1,"proposals":[proposal]}
    owner=db.one("SELECT id FROM agents LIMIT 1")["id"]
    created=service.create_tasks(pid,owner=owner)
    assert len(created)==1
    link=db.one("SELECT * FROM maintenance_task_links WHERE task_id=?",(created[0],))
    assert link["kind"]=="REVALIDATION"
    assert service.create_tasks(pid,owner=owner)==[]
    assert db.one("SELECT COUNT(*) AS n FROM tasks WHERE id=?",(created[0],))["n"]==1


def test_maintenance_approval_request_uses_single_transaction(tmp_path):
    from app.scientific_maintenance_controller import ScientificMaintenanceController
    from app.models import now
    db=Database(str(tmp_path/"maintenance-approval.db")); ResearchCycle(db); pid=_setup(db)
    wid=str(uuid.uuid4())
    db.execute(
        "INSERT INTO maintenance_work(id,kind,entity_type,entity_id,title,reason,success_criteria,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (wid,"REVALIDATION","CLAIM",str(uuid.uuid4()),"review","reason","criteria","PROPOSED",now(),now()))
    result=ScientificMaintenanceController(db).request_approval(wid,"founder")
    assert result["status"]=="APPROVAL_PENDING"
    assert result["approval_id"] is not None
    assert db.one("SELECT status FROM approvals WHERE id=?",(result["approval_id"],))["status"]=="PENDING"


def test_science_improvement_requires_existing_verified_evidence(tmp_path):
    from app.continuous_improvement import ContinuousImprovementService
    db=Database(str(tmp_path/"improvement-evidence.db")); ResearchCycle(db)
    service=ContinuousImprovementService(db)
    try:
        service.propose("Science change","SCIENCE","test hypothesis","metric","owner","missing")
        assert False, "missing evidence must be rejected"
    except ValueError as exc:
        assert "independently verified" in str(exc)


def test_maintenance_discover_materializes_proposal_contract(tmp_path, monkeypatch):
    from app.autonomous_scientific_maintenance import AutonomousScientificMaintenance
    from app.knowledge_freshness import KnowledgeFreshness
    from app.knowledge_impact import KnowledgeImpactAnalyzer
    from app.scientific_maintenance_controller import ScientificMaintenanceController
    db=Database(str(tmp_path/"maintenance-discover.db")); ResearchCycle(db); pid=_setup(db)
    claim_id=db.one("SELECT id FROM claims WHERE project_id=?",(pid,))["id"]
    monkeypatch.setattr(KnowledgeFreshness, "scan", lambda self, project_id: {
        "stale":[{"entity_type":"CLAIM","entity_id":claim_id}],
        "stale_count":1,
    })
    monkeypatch.setattr(KnowledgeImpactAnalyzer, "contradiction_scan", lambda self, project_id: {"impacts":[]})
    result=ScientificMaintenanceController(db).discover(pid)
    assert result["count"]==1
    assert result["created_or_existing"][0]["success_criteria"]
