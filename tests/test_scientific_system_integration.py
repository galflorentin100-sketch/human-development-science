import json
from app.database import Database
from app.workflow import ResearchCycle
from app.evidence_pipeline import EvidencePipeline
from app.knowledge_freshness import KnowledgeFreshness
from app.knowledge_impact import KnowledgeImpactAnalyzer
from app.scientific_admission import ScientificAdmissionGate
import uuid

def _setup(db):
    from app.models import now
    c,a,p=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(c,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(a,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(p,c,"o","ACTIVE",a,now()))
    return p

def test_evidence_excerpt_must_match_parsed_source(tmp_path):
    from app.models import now
    db=Database(str(tmp_path/"evidence-provenance.db")); ResearchCycle(db); pid=_setup(db)
    claim=str(uuid.uuid4()); source=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","HYPOTHESIS","PRELIMINARY",0.0,"PROPOSED",now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(source,"s","https://x/"+source,"PAPER","","test"))
    ep=EvidencePipeline(db); ep.ingest_text(source,"the verified source passage")
    try:
        ep.attach(claim,source,"invented passage")
        assert False
    except ValueError as exc:
        assert "not present in the parsed source" in str(exc)


def test_uncertain_verdict_cannot_resolve_verified(tmp_path):
    db=Database(str(tmp_path/"u.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4()); source=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","HYPOTHESIS","PRELIMINARY",0.0,"PROPOSED",now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(source,"s","https://x/"+source,"PAPER","","test"))
    ep=EvidencePipeline(db); ep.ingest_text(source,"text"); ev=ep.attach(claim,source,"excerpt")
    ep.review(ev["id"],"r1","VERIFIED","checked")
    ep.review(ev["id"],"r2","UNCERTAIN","uncertain")
    assert ep.resolve(ev["id"])["state"]=="UNCERTAIN"

def test_supported_claim_admission_requires_verified_nonconflicted_evidence(tmp_path):
    db=Database(str(tmp_path/"a.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    gate=ScientificAdmissionGate(db)
    result=gate.claim(claim)
    assert result["supported"] is False
    assert result["verified_evidence"]==0

def test_knowledge_impact_identifies_downstream_training(tmp_path):
    db=Database(str(tmp_path/"i.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4()); protocol=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    db.execute("""INSERT INTO training_protocols(id,project_id,name,target_construct_id,source_claim_id,intervention_id,mechanism_hypothesis,challenge_domain,dosage,progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,version,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(protocol,pid,"p",None,claim,None,"m","challenge","dose","progress","transfer","retention","safety","PRELIMINARY","PILOT",1,now()))
    impact=KnowledgeImpactAnalyzer(db).claim_impact(claim)
    assert any(x["id"]==protocol for x in impact["downstream"]["training_protocols"])
    assert impact["review_required"] is True

def test_freshness_register_and_scan(tmp_path):
    db=Database(str(tmp_path/"f.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","HYPOTHESIS","PRELIMINARY",0.0,"PROPOSED",now()))
    row=KnowledgeFreshness(db).register("CLAIM",claim,90,"tester")
    assert row["status"]=="ACTIVE"
    db.execute("UPDATE knowledge_freshness SET next_review_at=? WHERE id=?",( "2000-01-01T00:00:00+00:00",row["id"]))
    scan=KnowledgeFreshness(db).scan()
    assert scan["stale_count"]==1


def test_training_provenance_trace_reaches_protocol_evidence_and_sessions(tmp_path):
    from app.models import now
    from app.scientific_training_pipeline import ScientificTrainingPipeline
    from app.training import TrainingProtocolService

    db=Database(str(tmp_path/"trace.db")); ResearchCycle(db); pid=_setup(db)
    claim=str(uuid.uuid4()); source=str(uuid.uuid4())
    db.execute(
        "INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (claim,pid,"training claim","FACT","SUPPORTED",1.0,"SUPPORTED",now())
    )
    db.execute(
        "INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",
        (source,"s","https://x/"+source,"PAPER","","test")
    )
    ep=EvidencePipeline(db); ep.ingest_text(source,"evidence text")
    ev=ep.attach(claim,source,"excerpt")
    ep.review(ev["id"],"reviewer","VERIFIED","independent verification")

    protocol=TrainingProtocolService(db).create(
        pid,"protocol","mechanism","challenge","dose","progress",
        "transfer","retention","safety",evidence_level="SUPPORTED",
        source_claim_id=claim
    )
    from app.participant_governance import ParticipantGovernance
    ParticipantGovernance(db).register("participant-1","CONSENTED","v1")
    TrainingProtocolService(db).session(
        protocol["id"],"participant-1",1,"load","1",
        task_success=1.0,transfer_score=0.7,retention_score=0.6
    )

    graph=ScientificTrainingPipeline(db).trace(protocol["id"])
    assert graph["claim"]["id"]==claim
    assert any(x["layer"]=="CLAIM" and x["resolution"]["state"]=="VERIFIED" for x in graph["evidence"])
    assert len(graph["sessions"])==1
    assert graph["sessions"][0]["participant_ref"]=="participant-1"


def test_training_provenance_readiness_reports_missing_evidence(tmp_path):
    from app.models import now
    from app.scientific_training_pipeline import ScientificTrainingPipeline
    from app.training import TrainingProtocolService

    db=Database(str(tmp_path/"missing-trace.db")); ResearchCycle(db); pid=_setup(db)
    claim=str(uuid.uuid4())
    db.execute(
        "INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (claim,pid,"training claim","FACT","SUPPORTED",1.0,"SUPPORTED",now())
    )
    protocol=TrainingProtocolService(db).create(
        pid,"protocol","mechanism","challenge","dose","progress",
        "transfer","retention","safety",source_claim_id=claim
    )
    missing_ref=str(uuid.uuid4())
    TrainingProtocolService(db).attach_evidence(protocol["id"],"RCT",missing_ref)

    readiness=ScientificTrainingPipeline(db).readiness(protocol["id"])
    assert readiness["missing_evidence_count"]==1
    assert "missing_evidence" in readiness["blockers"]

def test_agent_output_submit_is_idempotent(tmp_path):
    from app.agent_output_gate import AgentOutputGate
    from app.models import now
    db=Database(str(tmp_path/"agent-output.db")); ResearchCycle(db); pid=_setup(db)
    task=str(uuid.uuid4()); run=str(uuid.uuid4())
    db.execute("INSERT INTO tasks(id,project_id,title,status,priority,success_criteria,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",(task,pid,"research","REVIEW",1.0,"review",now(),now()))
    agent_id=str(uuid.uuid4())
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(agent_id,"test-agent","researcher","test","[]","[\"READ\"]","1","ACTIVE",now()))
    db.execute("INSERT INTO agent_runs(id,agent_id,task_id,status,input_payload,output_payload,started_at,completed_at) VALUES (?,?,?,?,?,?,?,?)",(run,agent_id,task,"REVIEW","{}",'{\"result\":\"x\"}',now(),now()))
    first=AgentOutputGate(db).submit(run)
    second=AgentOutputGate(db).submit(run)
    assert first["id"]==second["id"]

def test_claim_revision_rejects_cross_project_evidence(tmp_path):
    from app.claim_revision import ClaimRevisionService
    from app.evidence_pipeline import EvidencePipeline
    from app.models import now
    db=Database(str(tmp_path/"claim-revision-isolation.db")); ResearchCycle(db); p1=_setup(db); p2=_setup(db)
    claim=str(uuid.uuid4()); source=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,p1,"claim","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),p2,"other","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(source,"s","https://x/"+source,"PAPER","","test"))
    ep=EvidencePipeline(db); ep.ingest_text(source,"evidence")
    other_claim=db.one("SELECT id FROM claims WHERE project_id=?",(p2,))
    ev=ep.attach(other_claim["id"],source,"excerpt")
    try:
        ClaimRevisionService(db).propose(claim,"revised","SUPPORTED","reason",[ev["id"]],"actor")
        assert False
    except ValueError as exc:
        assert "another project" in str(exc)

def test_agent_output_rejects_cross_project_evidence(tmp_path):
    from app.agent_output_gate import AgentOutputGate
    from app.evidence_pipeline import EvidencePipeline
    from app.models import now
    db=Database(str(tmp_path/"agent-output-isolation.db")); ResearchCycle(db); p1=_setup(db); p2=_setup(db)
    task=str(uuid.uuid4()); run=str(uuid.uuid4()); agent_id=str(uuid.uuid4())
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(agent_id,"test-agent","researcher","test","[]","[\"READ\"]","1","ACTIVE",now()))
    db.execute("INSERT INTO tasks(id,project_id,title,status,priority,success_criteria,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",(task,p1,"research","REVIEW",1.0,"review",now(),now()))
    claim=str(uuid.uuid4()); source=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,p2,"other","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(source,"s","https://x/"+source,"PAPER","","test"))
    ev=EvidencePipeline(db); ev.ingest_text(source,"evidence excerpt"); evidence=ev.attach(claim,source,"evidence excerpt")
    ev.review(evidence["id"],"independent-reviewer","VERIFIED","checked")
    db.execute("INSERT INTO agent_runs(id,agent_id,task_id,status,input_payload,output_payload,started_at,completed_at) VALUES (?,?,?,?,?,?,?,?)",(run,agent_id,task,"REVIEW","{}",json.dumps({"result":"x","evidence_refs":[evidence["id"]]}),now(),now()))
    review=AgentOutputGate(db).submit(run)
    try:
        AgentOutputGate(db).review(review["id"],"reviewer","ACCEPT","reason")
        assert False
    except ValueError as exc:
        assert "another project" in str(exc)
