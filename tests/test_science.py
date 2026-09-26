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
    ev=registry.intervention_evidence(i["id"],"PILOT","study-001","pilot evidence")
    assert ev["evidence_kind"]=="PILOT"


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
    pipeline.ingest_text(source_id,"source text")
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
    for idx,verdict in enumerate(("VERIFIED","REJECTED")):
        sid=str(uuid.uuid4())
        db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(sid,"s","https://example.com/"+sid,"PAPER","","test"))
        pipeline.ingest_text(sid,"source "+str(idx))
        ev=pipeline.attach(claim_id,sid,"excerpt")
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
    p.ingest_text(sid,"mixed")
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
