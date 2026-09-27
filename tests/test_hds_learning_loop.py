from app.database import Database
from app.workflow import ResearchCycle
from app.human_development import HumanDevelopmentService
from app.models import now


def test_competition_score_can_enter_scientific_loop_only_through_preregistered_binding(tmp_path):
    db=Database(str(tmp_path/"loop.db"))
    project=ResearchCycle(db).run("competition learning loop")["project"]
    svc=HumanDevelopmentService(db)

    program=svc.create_program(project["id"],"Measured Program","Outcome","PHYSICAL_PERFORMANCE","founder")
    challenge=svc.create_challenge(program["id"],"Timed challenge","Supervised","ENDURANCE",4,"Consent and stop criteria","founder")
    competition=svc.create_competition(project["id"],"Measured Competition","single_event","founder")
    event=svc.add_event(competition["id"],challenge["id"],1,"run_time")

    study="study-loop"; participant="study-participant"; measure="measure-loop"; binding="measure-binding"
    db.execute("""INSERT INTO studies(id,title,design,findings,created_at,project_id)
        VALUES (?,?,?,?,?,?)""",(study,"Competition study","pilot","",now(),project["id"]))
    db.execute("""INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at)
        VALUES (?,?,?,?,?)""",(participant,study,"participant-1","CONSENTED",now()))
    db.execute("""INSERT INTO study_measure_definitions
        (id,study_id,name,operational_definition,method,scale_type,reliability_note,validity_note,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (measure,study,"run_time","time","timed test","CONTINUOUS","test","test","PREREGISTERED",now()))
    db.execute("""INSERT INTO study_measure_bindings
        (id,study_id,measure_id,observation_type,timepoint,required)
        VALUES (?,?,?,?,?,?)""",(binding,study,measure,"TRAINING","POST",1))

    participant_row=svc.register_participant(competition["id"],"participant-1")
    svc.record_consent(participant_row["id"])
    svc.bind_participant_to_study(competition["id"],participant_row["id"],participant)
    svc.bind_event_measure(event["id"],study,measure,"TRAINING","POST")

    result=svc.record_score_as_outcome(event["id"],participant_row["id"],"run_time",120)
    assert result["score"]["score"]==120.0
    assert result["outcome"]["outcome_name"]=="run_time"
    assert result["outcome"]["observation_type"]=="TRAINING"
