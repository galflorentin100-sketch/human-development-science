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
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (str(uuid.uuid4()),p,"seed research claim","HYPOTHESIS","PRELIMINARY",0.1,"PROPOSED",now()))
    return p

def _verified_evidence(db, project_id, source_id, excerpt="verified research excerpt"):
    from app.evidence_pipeline import EvidencePipeline
    claim=db.one("SELECT id FROM claims WHERE project_id=? LIMIT 1",(project_id,))
    if not claim:
        raise AssertionError("test project must contain a seed claim")
    EvidencePipeline(db).ingest_text(source_id,excerpt)
    evidence=EvidencePipeline(db).attach(claim["id"],source_id,excerpt,"SUPPORTS",actor="researcher")
    EvidencePipeline(db).review(evidence["id"],"independent-reviewer","VERIFIED","verified against source")
    return evidence["id"]


def _accept_with_skeptic_gate(db, engine, workspace_id, synthesis_id):
    from app.skeptic import SkepticService
    skeptic=SkepticService(db).create(workspace_id,synthesis_id,"skeptic")
    SkepticService(db).record(
        skeptic["id"],
        ["alternative explanation"],
        ["missing evidence"],
        ["selection effects"],
    )
    SkepticService(db).review(skeptic["id"],"ACCEPTED","independent-reviewer","reviewed objections")
    return engine.review(synthesis_id,"founder","ACCEPTED","reviewed")

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

def test_research_queue_completion_is_bound_to_exact_workspace(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    from app.research_engine import ResearchEngine
    from app.research_queue import ResearchQueue
    db=Database(str(tmp_path/"queue-identity.db")); ResearchCycle(db); pid=_setup(db)
    queue=ResearchQueue(db); engine=ResearchEngine(db)
    first=queue.propose(pid,"same question","first","EVIDENCE_GAP")
    queue.approve(first["id"],"founder")
    started_first=queue.begin(first["id"],"founder")
    source=EvidencePipeline(db).register_source("Paper 1","https://example.org/1","Author",2025)
    engine.add_source(started_first["workspace"]["id"],source["id"])
    evidence_ref=_verified_evidence(db,pid,source["id"])
    syn=engine.synthesize(started_first["workspace"]["id"],"candidate","limits","uncertain","researcher",evidence_refs=[evidence_ref])
    _accept_with_skeptic_gate(db,engine,started_first["workspace"]["id"],syn["id"])
    assert queue.get(first["id"])["status"]=="DONE"

    second=queue.propose(pid,"same question","second","EVIDENCE_GAP")
    queue.approve(second["id"],"founder")
    started_second=queue.begin(second["id"],"founder")
    assert started_second["workspace"]["id"] != started_first["workspace"]["id"]
    assert queue.get(second["id"])["status"]=="IN_PROGRESS"
    assert queue.get(first["id"])["status"]=="DONE"


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
    evidence_ref=_verified_evidence(db,pid,source["id"])
    syn=engine.synthesize(ws["id"],"candidate synthesis","small sample","causal effect not established","researcher",evidence_refs=[evidence_ref])
    assert syn["status"]=="CANDIDATE"
    accepted=_accept_with_skeptic_gate(db,engine,ws["id"],syn["id"])
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
    evidence_ref=_verified_evidence(db,pid,source["id"])
    syn=engine.synthesize(ws["id"],"Candidate synthesis","limitations","uncertain","researcher",evidence_refs=[evidence_ref])
    _accept_with_skeptic_gate(db,engine,ws["id"],syn["id"])
    EvidencePipeline(db).ingest_text(source["id"],"Relevant excerpt")
    # Create a real, independently verified evidence reference before promotion.
    from app.evidence_pipeline import EvidencePipeline
    claim_id=str(uuid.uuid4())
    from app.models import now
    db.execute("INSERT INTO claims(id,project_id,statement,status,classification,confidence,review_required,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
               (claim_id,pid,"placeholder","SUPPORTED","INFERENCE",1.0,0,now(),now()))
    EvidencePipeline(db).ingest_text(source["id"],"Relevant excerpt")
    evidence=EvidencePipeline(db).attach(claim_id,source["id"],"Relevant excerpt","SUPPORTS",actor="researcher")
    EvidencePipeline(db).review(evidence["id"],"founder","VERIFIED","verified against source")
    # Rebuild the synthesis with the verified evidence reference.
    db.execute("UPDATE research_syntheses SET evidence_refs=? WHERE id=?",(json.dumps([evidence["id"]]),syn["id"]))
    finding=engine.promote_to_candidate_finding(syn["id"],"knowledge-manager")
    assert finding["status"]=="CANDIDATE"
    assert finding["classification"]=="INFERENCE"

def test_research_agent_lookup_uses_canonical_role(tmp_path):
    from app.research_engine import ResearchEngine
    from app.research_agent import ResearchAgentService
    from app.models import now
    db=Database(str(tmp_path/"agent-lookup.db")); ResearchCycle(db); pid=_setup(db)
    aid=str(uuid.uuid4())
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
               (aid,"researcher","researcher","research","[]","[\\\"READ\\\"]","1","ACTIVE",now()))
    ws=ResearchEngine(db).create(pid,"Question",owner="founder")
    ResearchEngine(db).activate(ws["id"],"founder")
    result=ResearchAgentService(db).create_task(ws["id"])
    assert result["agent_id"]==aid
    assert result["task"]["assigned_agent_id"]==aid


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

def test_inference_causal_finding_cannot_be_promoted_to_claim(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    from app.research_engine import ResearchEngine
    from app.finding_claim_bridge import FindingClaimBridge
    import json
    db=Database(str(tmp_path/"causal-bridge.db")); ResearchCycle(db); pid=_setup(db)
    source=EvidencePipeline(db).register_source("Paper","https://example.org/causal","Author",2025)
    claim_id=str(uuid.uuid4())
    from app.models import now
    db.execute("INSERT INTO claims(id,project_id,statement,status,classification,confidence,review_required,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
               (claim_id,pid,"source placeholder","SUPPORTED","INFERENCE",1.0,0,now(),now()))
    ev=EvidencePipeline(db).attach(claim_id,source["id"],"excerpt","SUPPORTS",actor="researcher")
    EvidencePipeline(db).review(ev["id"],"founder","VERIFIED","verified")
    from app.research import ResearchFindingService
    finding=ResearchFindingService(db).create(
        pid,"The intervention causes improved resilience",
        classification="INFERENCE",source_type="LITERATURE",source_id=None,
        evidence_refs=[ev["id"]],created_by="researcher")
    ResearchFindingService(db).review(finding["id"],"founder","ACCEPTED","evidence verified")
    try:
        FindingClaimBridge(db).propose_claim(finding["id"],"knowledge-manager")
        assert False
    except ValueError as exc:
        assert "causal claim" in str(exc)

def test_finding_promotion_requires_evidence_audit(tmp_path):
    import json
    from app.evidence_pipeline import EvidencePipeline
    from app.research_engine import ResearchEngine
    from app.skeptic import SkepticService
    db=Database(str(tmp_path/"gate.db")); ResearchCycle(db); pid=_setup(db)
    engine=ResearchEngine(db)
    ws=engine.create(pid,"Does friction affect adherence?",owner="researcher"); engine.activate(ws["id"],"researcher")
    source=EvidencePipeline(db).register_source("Paper","https://example.org/friction","Author",2025)
    engine.add_source(ws["id"],source["id"])
    evidence_ref=_verified_evidence(db,pid,source["id"])
    syn=engine.synthesize(ws["id"],"candidate","limitations","uncertain","researcher",evidence_refs=[evidence_ref])
    _accept_with_skeptic_gate(db,engine,ws["id"],syn["id"])
    db.execute("UPDATE research_syntheses SET evidence_refs='[]' WHERE id=?",(syn["id"],))
    try:
        engine.promote_to_candidate_finding(syn["id"],"knowledge-manager")
        assert False
    except ValueError as exc:
        assert "evidence_audit" in str(exc)


def test_research_review_pipeline_creates_two_independent_tasks(tmp_path):
    from app.research_engine import ResearchEngine
    from app.research_review_pipeline import ResearchReviewPipeline
    from app.models import now
    db=Database(str(tmp_path/"review_tasks.db")); ResearchCycle(db); pid=_setup(db)
    for aid,role in [(str(uuid.uuid4()),"skeptic"),(str(uuid.uuid4()),"evidence-auditor")]:
        db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (aid,role,role,"review","[]","[\"READ\"]","1","ACTIVE",now()))
    engine=ResearchEngine(db)
    ws=engine.create(pid,"Question",owner="researcher"); engine.activate(ws["id"],"researcher")
    from app.evidence_pipeline import EvidencePipeline
    source=EvidencePipeline(db).register_source("Paper","https://example.org/review","Author",2025)
    engine.add_source(ws["id"],source["id"])
    syn=engine.synthesize(ws["id"],"Synthesis","limits","uncertain","researcher")
    result=ResearchReviewPipeline(db).create_for_synthesis(syn["id"])
    assert len(result["tasks"])==2
    roles={x["owner"] for x in result["tasks"]}
    assert len(roles)==2


def test_add_source_with_content_ingests_atomically(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    from app.research_engine import ResearchEngine
    db=Database(str(tmp_path/"source_content.db")); ResearchCycle(db); pid=_setup(db)
    engine=ResearchEngine(db)
    ws=engine.create(pid,"Question",owner="researcher")
    engine.activate(ws["id"],"researcher")
    source=EvidencePipeline(db).register_source("Paper","https://example.org/content","Author",2025)
    linked=engine.add_source(ws["id"],source["id"],content="Verified source text")
    assert linked["content_hash"]
    parsed=db.one("SELECT content,state FROM evidence_sources WHERE source_id=?",(source["id"],))
    assert parsed["content"]=="Verified source text"
    assert parsed["state"]=="PARSED"


def test_ingest_text_deduplicates_source_content(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    db=Database(str(tmp_path/"source_dedupe.db")); ResearchCycle(db)
    pid=_setup(db)
    registered=EvidencePipeline(db).register_source("Paper","https://example.org/dedupe","Author",2025)
    first=EvidencePipeline(db).ingest_text(registered["id"],"same source text")
    second=EvidencePipeline(db).ingest_text(registered["id"],"same source text")
    assert first["id"]==second["id"]
    rows=db.all("SELECT id FROM evidence_sources WHERE source_id=? AND content_hash=?",(registered["id"],first["content_hash"]))
    assert len(rows)==1


def test_research_review_pipeline_rolls_back_partial_task_creation(tmp_path):
    from app.research_engine import ResearchEngine
    from app.research_review_pipeline import ResearchReviewPipeline
    from app.models import now
    from app.evidence_pipeline import EvidencePipeline
    db=Database(str(tmp_path/"review-rollback.db")); ResearchCycle(db); pid=_setup(db)
    # Keep a skeptic reviewer available but make the second reviewer unavailable.
    db.execute("UPDATE agents SET status='INACTIVE' WHERE role IN ('evidence-auditor','evidence')")
    ws=ResearchEngine(db).create(pid,"Question",owner="researcher")
    ResearchEngine(db).activate(ws["id"],"researcher")
    source=EvidencePipeline(db).register_source("Paper","https://example.org/rollback","Author",2025)
    ResearchEngine(db).add_source(ws["id"],source["id"])
    syn=ResearchEngine(db).synthesize(ws["id"],"Synthesis","limits","uncertain","researcher")
    try:
        ResearchReviewPipeline(db).create_for_synthesis(syn["id"])
        assert False, "missing reviewer should fail"
    except ValueError as exc:
        assert "review agent" in str(exc)
    assert db.one("SELECT COUNT(*) AS n FROM research_review_tasks WHERE synthesis_id=?",(syn["id"],))["n"]==0
    assert db.one("SELECT COUNT(*) AS n FROM tasks WHERE project_id=? AND title LIKE ?",(pid,"%"+syn["id"]))["n"]==0
