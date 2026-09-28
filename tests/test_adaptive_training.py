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
