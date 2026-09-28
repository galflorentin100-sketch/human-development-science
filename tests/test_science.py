from app.database import Database
from app.workflow import ResearchCycle
from app.science import ScientificRegistry

def test_scientific_registry_tracks_construct_measure_and_version(tmp_path):
    db=Database(str(tmp_path/"science.db")); ResearchCycle(db)
    registry=ScientificRegistry(db)
    c=registry.construct("Goal-directed self-regulation","Ability to direct and maintain behavior toward a chosen goal despite obstacles.")
    assert c["version"]==1
    registry.measure(c["id"],"Goal execution rate","Completed planned actions / planned actions","Structured daily log","percent","To be established","To be established")
    updated=registry.version_construct(c["id"],"Ability to direct and maintain behavior toward a chosen goal despite obstacles while adapting strategy when conditions change.","Behavioral task plus real-world transfer","Expanded construct definition")
    assert updated["version"]==2
    assert db.one("SELECT COUNT(*) AS n FROM construct_versions WHERE construct_id=?",(c["id"],))["n"]==2

def test_intervention_cannot_claim_unknown_evidence_level(tmp_path):
    db=Database(str(tmp_path/"science2.db")); ResearchCycle(db)
    registry=ScientificRegistry(db)
    try:
        registry.intervention("x","rationale","mechanism","PROVEN","daily","adults")
        assert False
    except ValueError as exc:
        assert "evidence level" in str(exc)

def test_intervention_evidence_is_structured(tmp_path):
    db=Database(str(tmp_path/"science3.db")); ResearchCycle(db)
    registry=ScientificRegistry(db)
    i=registry.intervention("x","rationale","mechanism","PLAUSIBLE","daily","adults")
    ev=registry.intervention_evidence(i["id"],"EXPERT_JUDGMENT","expert-001","expert evidence")
    assert ev["evidence_kind"]=="EXPERT_JUDGMENT"


def test_scientific_interpretation_blocks_unsupported_causality():
    from app.scientific_ai import ScientificAIGuard
    guard=ScientificAIGuard()
    try:
        guard.validate_interpretation("The intervention caused a durable improvement.")
        assert False
    except ValueError as exc:
        assert "unsupported" in str(exc)

def test_scientific_interpretation_allows_qualified_inference():
    from app.scientific_ai import ScientificAIGuard
    statement=ScientificAIGuard().validate_interpretation(
        "The randomized comparison was associated with a larger mean change.",
        causal_design=False,
        evidence_refs=("analysis-1",),
    )
    assert statement.classification=="INFERENCE"


def test_claim_evidence_resolution_requires_reviewer_state(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    from app.claim_state import ClaimStateService
    db=Database(str(tmp_path/"evidence.db")); ResearchCycle(db)
    company=db.one("SELECT id FROM companies LIMIT 1")
    project=db.one("SELECT id FROM projects LIMIT 1")
    if not project:
        from app.models import now
        cid=company["id"] if company else "company-test"
        if not company:
            db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(cid,"c","m","v","p",now()))
        agent=db.one("SELECT id FROM agents LIMIT 1")
        if not agent:
            db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",("agent-test","a","r","m","[]","[]","1","ACTIVE",now()))
            agent={"id":"agent-test"}
        import uuid
        pid=str(uuid.uuid4())
        db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(pid,cid,"test","ACTIVE",agent["id"],now()))
        project={"id":pid}
    import uuid
    claim_id=str(uuid.uuid4()); source_id=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim_id,project["id"],"x","HYPOTHESIS","PRELIMINARY",0.5,"PROPOSED",now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(source_id,"s","https://example.com/"+source_id,"PAPER","","test"))
    pipeline=EvidencePipeline(db)
    pipeline.ingest_text(source_id, "source text; excerpt")
    ev=pipeline.attach(claim_id,source_id,"excerpt")
    assert pipeline.resolve(ev["id"])["state"]=="UNREVIEWED"
    pipeline.review(ev["id"],"reviewer-1","VERIFIED","checked")
    assert ClaimStateService(db).evidence_state(claim_id)["state"]=="SUPPORTED_EVIDENCE"

def test_conflicting_evidence_forces_uncertain_claim(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    db=Database(str(tmp_path/"conflict.db")); ResearchCycle(db)
    from app.models import now
    import uuid
    company_id=str(uuid.uuid4()); agent_id=str(uuid.uuid4()); project_id=str(uuid.uuid4()); claim_id=str(uuid.uuid4())
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(company_id,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(agent_id,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(project_id,company_id,"o","ACTIVE",agent_id,now()))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim_id,project_id,"x","HYPOTHESIS","PRELIMINARY",0.5,"SUPPORTED",now()))
    pipeline=EvidencePipeline(db)
    for idx,verdict in enumerate(("VERIFIED","VERIFIED")):
        sid=str(uuid.uuid4())
        db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(sid,"s","https://example.com/"+sid,"PAPER","","test"))
        pipeline.ingest_text(sid,"source "+str(idx)+" excerpt")
        stance="SUPPORTS" if idx==0 else "CONTRADICTS"
        ev=pipeline.attach(claim_id,sid,"excerpt",stance)
        pipeline.review(ev["id"],"reviewer-"+str(idx),verdict,"reviewed")
    assert pipeline.claim_evidence_state(claim_id)["conflicted"]==1
    assert db.one("SELECT status FROM claims WHERE id=?",(claim_id,))["status"]=="UNCERTAIN"

def test_training_protocol_requires_transfer_retention_and_safety(tmp_path):
    from app.training import TrainingProtocolService
    db=Database(str(tmp_path/"training.db")); ResearchCycle(db)
    from app.models import now
    import uuid
    company_id=str(uuid.uuid4()); agent_id=str(uuid.uuid4()); project_id=str(uuid.uuid4())
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(company_id,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(agent_id,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(project_id,company_id,"o","ACTIVE",agent_id,now()))
    svc=TrainingProtocolService(db)
    try:
        svc.create(project_id,"p","mechanism","fatigue","daily","progress","", "8 weeks","safe")
        assert False
    except ValueError as exc:
        assert "required" in str(exc)
    p=svc.create(project_id,"p","mechanism","fatigue","daily","progress","real-world task","8 weeks","safety")
    assert svc.readiness(p["id"])["ready_for_pilot"] is True


def test_training_protocol_cannot_be_supported_without_transfer_and_retention(tmp_path):
    from app.training import TrainingProtocolService
    db=Database(str(tmp_path/"promotion.db")); ResearchCycle(db)
    from app.models import now
    import uuid
    cid,aid,pid=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(cid,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(aid,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(pid,cid,"o","ACTIVE",aid,now()))
    svc=TrainingProtocolService(db)
    claim_id=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim_id,pid,"pilot basis","HYPOTHESIS","PRELIMINARY",0.1,"PROPOSED",now()))
    p=svc.create(pid,"protocol","mechanism","uncertainty","dose","progress","real-world","8 weeks","safety",source_claim_id=claim_id)
    svc.promote(p["id"],"PILOT","reviewer","pilot begins")
    try:
        svc.promote(p["id"],"SUPPORTED","reviewer","support")
        assert False
    except ValueError as exc:
        assert "evidence" in str(exc) or "sessions" in str(exc)


def test_evidence_uncertain_plus_verified_remains_uncertain(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    import uuid
    from app.models import now
    db=Database(str(tmp_path/"mixed-review.db")); ResearchCycle(db)
    cid,aid,pid=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(cid,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(aid,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(pid,cid,"o","ACTIVE",aid,now()))
    claim_id=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim_id,pid,"x","HYPOTHESIS","PRELIMINARY",0.5,"PROPOSED",now()))
    p=EvidencePipeline(db)
    sid=str(uuid.uuid4())
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(sid,"s","https://example.com/"+sid,"PAPER","","test"))
    p.ingest_text(sid, "mixed; excerpt")
    e=p.attach(claim_id,sid,"excerpt")
    p.review(e["id"],"r1","VERIFIED","checked")
    p.review(e["id"],"r2","UNCERTAIN","uncertain")
    assert p.resolve(e["id"])["state"]=="UNCERTAIN"


def test_knowledge_freshness_flags_due_review(tmp_path):
    from app.knowledge_freshness import KnowledgeFreshness
    import uuid
    from app.models import now
    db=Database(str(tmp_path/"fresh.db")); ResearchCycle(db)
    cid,aid,pid=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(cid,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(aid,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(pid,cid,"o","ACTIVE",aid,now()))
    claim_id=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim_id,pid,"x","HYPOTHESIS","PRELIMINARY",0.5,"PROPOSED",now()))
    k=KnowledgeFreshness(db)
    k.register("CLAIM",claim_id,1)
    db.execute("UPDATE knowledge_freshness SET next_review_at=? WHERE entity_type='CLAIM' AND entity_id=?",( "2000-01-01T00:00:00+00:00",claim_id))
    scan=k.scan()
    assert scan["stale_count"]==1


def test_knowledge_impact_finds_downstream_training(tmp_path):
    from app.knowledge_impact import KnowledgeImpactAnalyzer
    import uuid
    from app.models import now
    db=Database(str(tmp_path/"impact.db")); ResearchCycle(db)
    cid,aid,pid,claim_id=[str(uuid.uuid4()) for _ in range(4)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(cid,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(aid,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(pid,cid,"o","ACTIVE",aid,now()))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim_id,pid,"x","HYPOTHESIS","PRELIMINARY",0.5,"PROPOSED",now()))
    from app.training import TrainingProtocolService
    p=TrainingProtocolService(db).create(pid,"t","mechanism","stress","dose","progress","transfer","retention","safety",source_claim_id=claim_id)
    impact=KnowledgeImpactAnalyzer(db).claim_impact(claim_id)
    assert any(x["id"]==p["id"] for x in impact["downstream"]["training_protocols"])
    assert impact["review_required"] is True


def test_scientific_system_health_is_read_only_and_flags_gaps(tmp_path):
    from app.scientific_system_health import ScientificSystemHealth
    db=Database(str(tmp_path/"health.db")); ResearchCycle(db)
    result=ScientificSystemHealth(db).snapshot()
    assert result["status"] in {"NOMINAL","REVIEW_REQUIRED"}
    assert result["policy"].startswith("health reports")
    assert result["maintenance_proposals"] >= 0


def test_autonomous_maintenance_materializes_only_auditable_work(tmp_path):
    from app.autonomous_scientific_maintenance import AutonomousScientificMaintenance
    db=Database(str(tmp_path/"maintenance.db")); ResearchCycle(db)
    result=AutonomousScientificMaintenance(db).materialize()
    assert result["policy"].startswith("materialization creates")
    for wid in result["created"]:
        row=db.one("SELECT status FROM maintenance_work WHERE id=?",(wid,))
        assert row["status"]=="PROPOSED"


def test_scientific_integrity_rejects_supported_claim_without_verified_support(tmp_path):
    from app.scientific_integrity import ScientificIntegrityChecker
    from app.models import now
    import uuid
    db=Database(str(tmp_path/"integrity.db")); ResearchCycle(db)
    company,agent,project,claim=[str(uuid.uuid4()) for _ in range(4)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(company,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(agent,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(project,company,"o","ACTIVE",agent,now()))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,project,"x","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    result=ScientificIntegrityChecker(db).project(project)
    assert result["integrity"]=="REVIEW_REQUIRED"
    assert any(x["type"]=="SUPPORTED_CLAIM_WITHOUT_EVIDENCE" for x in result["issues"])


def test_scientific_interpretation_does_not_flag_frameworks_as_works(tmp_path):
    from app.scientific_ai import ScientificAIGuard
    statement=ScientificAIGuard().validate_interpretation(
        "The frameworks were compared descriptively.",
        causal_design=False,
    )
    assert statement.classification=="INFERENCE"



def test_claim_admission_requires_supporting_evidence(tmp_path):
    from app.evidence_pipeline import EvidencePipeline
    from app.scientific_admission import ScientificAdmissionGate
    from app.models import now
    import uuid
    db=Database(str(tmp_path/"admission.db")); cycle=ResearchCycle(db)
    project=cycle.run("claim admission")["project"]
    claim_id=str(uuid.uuid4()); source_id=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (claim_id,project["id"],"claim","INFERENCE","VERIFIED",0.8,"SUPPORTED",now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",
               (source_id,"contradictory","https://example.com/"+source_id,"PAPER","","test"))
    pipeline=EvidencePipeline(db)
    pipeline.ingest_text(source_id,"contradictory excerpt")
    evidence=pipeline.attach(claim_id,source_id,"contradictory excerpt",stance="CONTRADICTS")
    pipeline.review(evidence["id"],"independent-reviewer","VERIFIED","verified")
    admission=ScientificAdmissionGate(db).claim(claim_id)
    assert admission["verified_support"]==0
    assert admission["verified_contradict"]==1
    assert admission["supported"] is False


def test_completion_gate_uses_structured_scientific_validation(tmp_path):
    from app.database import Database
    from app.models import now
    from app.scientific_completion import ScientificCompletionGate
    from app.experiment_engine import ExperimentEngine
    db=Database(str(tmp_path/"completion.db"))
    ExperimentEngine(db)
    ts=now()
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",("p1","hds","objective","RUNNING","chief-scientist",ts))
    db.execute("INSERT INTO tasks(id,project_id,title,assigned_agent_id,priority,status,success_criteria,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",("t1","p1","validation task","chief-scientist",1.0,"COMPLETED","validate",ts,ts))
    assert "no_structured_scientific_validation" in ScientificCompletionGate(db).evaluate("p1")["blockers"]
    db.execute("""INSERT INTO hds_experiments
        (id,project_id,research_question,hypothesis,design,population,intervention,comparison,outcomes,analysis_plan,status,preregistered,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",("e1","p1","question","hypothesis","design","population","intervention","comparison","outcomes","{}","COMPLETED",1,ts,ts))
    db.execute("INSERT INTO hds_experiment_results(id,experiment_id,outcome,interpretation,evidence_refs,created_at) VALUES (?,?,?,?,?,?)",("r1","e1","outcome","interpretation","[]",ts))
    result=ScientificCompletionGate(db).evaluate("p1")
    assert result["ready"] is True
    assert result["checks"]["completed_validation_work"] == 1


def test_research_synthesis_acceptance_requires_evidence_and_skeptic_gates(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.research_engine import ResearchEngine
    from app.evidence_pipeline import EvidencePipeline
    from app.models import now
    import uuid

    db=Database(str(tmp_path/"synthesis-gates.db")); cycle=ResearchCycle(db)
    project=cycle.run("synthesis gates")["project"]
    source=EvidencePipeline(db).register_source(
        "Gate source","https://example.org/synthesis-gates-"+str(uuid.uuid4())
    )
    EvidencePipeline(db).ingest_text(source["id"],"verified excerpt")
    claim=db.one("SELECT id FROM claims WHERE project_id=? LIMIT 1",(project["id"],))
    evidence=EvidencePipeline(db).attach(claim["id"],source["id"],"verified excerpt")
    EvidencePipeline(db).review(evidence["id"],"independent-reviewer","VERIFIED","checked")

    engine=ResearchEngine(db)
    workspace=engine.create(project["id"],"Does the evidence support the synthesis?")
    engine.activate(workspace["id"],"researcher")
    engine.add_source(workspace["id"],source["id"],content="verified excerpt")
    synthesis=engine.synthesize(workspace["id"],"Evidence-grounded synthesis","limitations","uncertainty",created_by="researcher",evidence_refs=[evidence["id"]])

    try:
        engine.review(synthesis["id"],"approver","ACCEPTED","accept")
        assert False, "accepted synthesis must require an accepted skeptic review"
    except ValueError as exc:
        assert "skeptic review" in str(exc)

    ts=now()
    db.execute(
        """INSERT INTO research_skeptic_reviews
        (id,workspace_id,synthesis_id,project_id,reviewer_agent_id,status,objections,missing_evidence,alternative_explanations,created_at,reviewed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()),workspace["id"],synthesis["id"],project["id"],"skeptic",
         "ACCEPTED","[]","[]","[]",ts,ts),
    )
    accepted=engine.review(synthesis["id"],"approver","ACCEPTED","accept")
    assert accepted["status"]=="ACCEPTED"
