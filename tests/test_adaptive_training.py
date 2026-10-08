from app.database import Database
from app.workflow import ResearchCycle
from app.human_development import HumanDevelopmentService
from app.adaptive_training import ChallengeExecutionService, AdaptiveTrainingService

def test_challenge_execution_always_requires_safety_gate(tmp_path):
    db=Database(str(tmp_path/"hds.db")); project=ResearchCycle(db).run("safety")["project"]; h=HumanDevelopmentService(db)
    p=h.create_program(project["id"],"P","O","RESILIENCE","u")
    ch=h.create_challenge(p["id"],"C","D","physical",5,"stop","u")
    comp=h.create_competition(project["id"],"Comp","format","u"); h.add_event(comp["id"],ch["id"],1,"points")
    participant=h.register_participant(comp["id"],"person"); h.record_consent(participant["id"])
    try: ChallengeExecutionService(db).start(project["id"],ch["id"],participant["id"])
    except ValueError as e: assert "safety approval" in str(e)
    else: assert False
    h.create_safety_control(project["id"],ch["id"],"LOW","stop"); h.approve_safety(ch["id"],"reviewer","APPROVED","reviewed")
    h.update_participant_safety(participant["id"],"ELIGIBLE","ASSIGNED","NOT_REQUIRED")
    execution=ChallengeExecutionService(db).start(project["id"],ch["id"],participant["id"],"actor-1")
    assert execution["status"]=="RUNNING"
    stopped=ChallengeExecutionService(db).stop(execution["id"],"participant requested stop","actor-1")
    assert db.one("SELECT actor FROM audit_logs WHERE entity_id=? AND event_type='hds.challenge.stopped'",(execution["id"],))["actor"]=="actor-1"
    assert stopped["status"]=="STOPPED"

def test_adaptive_training_requires_sufficient_signal(tmp_path):
    db=Database(str(tmp_path/"hds.db")); project=ResearchCycle(db).run("training")["project"]
    from app.training import TrainingProtocolService
    protocol=TrainingProtocolService(db).create(project["id"],"P","hypothesis","domain","dose","increase when ready","transfer","retention","safety",target_construct_id=None)
    result=AdaptiveTrainingService(db).recommend(protocol["id"],"person")
    assert result["decision"]=="HOLD"


def test_emergency_stop_stops_all_running_project_executions(tmp_path):
    db=Database(str(tmp_path/"emergency.db")); project=ResearchCycle(db).run("emergency")["project"]; h=HumanDevelopmentService(db)
    p=h.create_program(project["id"],"P","O","RESILIENCE","u")
    ch=h.create_challenge(p["id"],"C","D","physical",5,"stop","u")
    comp=h.create_competition(project["id"],"Comp","format","u"); h.add_event(comp["id"],ch["id"],1,"points")
    participant=h.register_participant(comp["id"],"person"); h.record_consent(participant["id"])
    h.create_safety_control(project["id"],ch["id"],"LOW","stop"); h.approve_safety(ch["id"],"reviewer","APPROVED","reviewed")
    h.update_participant_safety(participant["id"],"ELIGIBLE","ASSIGNED","NOT_REQUIRED")
    first=ChallengeExecutionService(db).start(project["id"],ch["id"],participant["id"],"actor")
    second_id="exec-second"
    db.execute("""INSERT INTO hds_challenge_executions
        (id,project_id,challenge_id,participant_id,status,started_at,created_at)
        VALUES (?,?,?,?,?,?,?)""",(second_id,project["id"],ch["id"],participant["id"],"RUNNING","now","now"))
    result=ChallengeExecutionService(db).emergency_stop(project["id"],"unsafe environment","safety-officer")
    assert result["count"]==2
    rows=db.all("SELECT status,stop_reason FROM hds_challenge_executions WHERE project_id=?",(project["id"],))
    assert all(r["status"]=="STOPPED" and r["stop_reason"]=="unsafe environment" for r in rows)
    assert db.one("SELECT COUNT(*) AS n FROM audit_logs WHERE event_type='hds.challenge.emergency_stopped'")["n"]==2


def test_adaptive_training_change_requires_project_scope_consent_and_safety_checks(tmp_path):
    db=Database(str(tmp_path/"adaptive-gate.db"))
    project=ResearchCycle(db).run("adaptive gate")["project"]
    other=ResearchCycle(db).run("other")["project"]
    from app.training import TrainingProtocolService
    from app.participant_governance import ParticipantGovernance
    protocol=TrainingProtocolService(db).create(project["id"],"P","hypothesis","domain","dose","increase when ready","transfer","retention","safety")
    ParticipantGovernance(db).register("person","v1")
    try:
        AdaptiveTrainingService(db).apply(other["id"],protocol["id"],"person",2,"test",{"clear":True})
        assert False
    except ValueError as exc:
        assert "another project" in str(exc)
    try:
        AdaptiveTrainingService(db).apply(project["id"],protocol["id"],"person",2,"test")
        assert False
    except ValueError as exc:
        assert "safety checks" in str(exc)


def test_cross_project_participant_cannot_execute_challenge(tmp_path):
    db=Database(str(tmp_path/"cross-project-participant.db"))
    project=ResearchCycle(db).run("project-a")["project"]
    other=ResearchCycle(db).run("project-b")["project"]
    h=HumanDevelopmentService(db)
    p=h.create_program(project["id"],"P","O","RESILIENCE","u")
    ch=h.create_challenge(p["id"],"C","D","physical",5,"stop","u")
    comp=h.create_competition(project["id"],"Comp","format","u")
    h.add_event(comp["id"],ch["id"],1,"points")
    participant=h.register_participant(comp["id"],"person-a")
    h.record_consent(participant["id"])
    h.create_safety_control(project["id"],ch["id"],"LOW","stop")
    h.approve_safety(ch["id"],"reviewer","APPROVED","reviewed")
    h.update_participant_safety(participant["id"],"ELIGIBLE","ASSIGNED","NOT_REQUIRED")

    foreign_program=h.create_program(other["id"],"P2","O2","RESILIENCE","u")
    foreign_challenge=h.create_challenge(foreign_program["id"],"C2","D2","physical",5,"stop","u")
    foreign_comp=h.create_competition(other["id"],"Comp2","format","u")
    h.add_event(foreign_comp["id"],foreign_challenge["id"],1,"points")
    foreign_participant=h.register_participant(foreign_comp["id"],"person-b")
    h.record_consent(foreign_participant["id"])
    h.create_safety_control(other["id"],foreign_challenge["id"],"LOW","stop")
    h.approve_safety(foreign_challenge["id"],"reviewer","APPROVED","reviewed")
    h.update_participant_safety(foreign_participant["id"],"ELIGIBLE","ASSIGNED","NOT_REQUIRED")

    try:
        ChallengeExecutionService(db).start(project["id"],ch["id"],foreign_participant["id"])
        assert False, "cross-project participant execution must be denied"
    except ValueError as exc:
        assert "participant does not belong to project" in str(exc)


def test_cross_project_study_participant_cannot_bind_to_competition(tmp_path):
    db=Database(str(tmp_path/"cross-project-study-binding.db"))
    project=ResearchCycle(db).run("project-a")["project"]
    other=ResearchCycle(db).run("project-b")["project"]
    h=HumanDevelopmentService(db)
    comp=h.create_competition(project["id"],"Comp","format","u")
    participant=h.register_participant(comp["id"],"person-a")
    from uuid import uuid4
    from app.models import now
    source_a=str(uuid4())
    source_b=str(uuid4())
    db.execute(
        "INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",
        (source_a,"Source A","https://example.com/source-a","test",2026,"OTHER",now(),"test fixture"),
    )
    db.execute(
        "INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",
        (source_b,"Source B","https://example.com/source-b","test",2026,"OTHER",now(),"test fixture"),
    )
    study_a=str(uuid4())
    study_b=str(uuid4())
    db.execute(
        "INSERT INTO studies(id,source_id,title,design,population,findings,created_at,project_id) VALUES (?,?,?,?,?,?,?,?)",
        (study_a,source_a,"Study A","design","population","",now(),project["id"]),
    )
    db.execute(
        "INSERT INTO studies(id,source_id,title,design,population,findings,created_at,project_id) VALUES (?,?,?,?,?,?,?,?)",
        (study_b,source_b,"Study B","design","population","",now(),other["id"]),
    )
    sp_b=str(uuid4())
    db.execute(
        "INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",
        (sp_b,study_b,"foreign-person","CONSENTED",now()),
    )
    try:
        h.bind_participant_to_study(comp["id"],participant["id"],sp_b)
        assert False, "cross-project study participant binding must be denied"
    except ValueError as exc:
        assert "same project" in str(exc)
