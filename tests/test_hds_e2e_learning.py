from app.database import Database
from app.workflow import ResearchCycle
from app.models import now
from app.outcome_feedback import OutcomeFeedbackService

def test_measured_outcome_feeds_candidate_research_without_claim_promotion(tmp_path):
    db=Database(str(tmp_path/"e2e.db"))
    project=ResearchCycle(db).run("e2e")["project"]
    study="study-e2e"
    participant="participant-e2e"
    measure="measure-e2e"
    binding="binding-e2e"
    db.execute("""INSERT INTO studies(id,title,design,findings,created_at,project_id)
                  VALUES (?,?,?,?,?,?)""",(study,"E2E study","pilot","",now(),project["id"]))
    db.execute("""INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at)
                  VALUES (?,?,?,?,?)""",(participant,study,"p1","CONSENTED",now()))
    db.execute("""INSERT INTO study_measure_definitions
                  (id,study_id,name,operational_definition,method,scale_type,reliability_note,validity_note,status,created_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (measure,study,"resilience_score","observed score","assessment","CONTINUOUS","known","known","PREREGISTERED",now()))
    db.execute("""INSERT INTO study_measure_bindings
                  (id,study_id,measure_id,observation_type,timepoint,required)
                  VALUES (?,?,?,?,?,?)""",(binding,study,measure,"TRAINING","POST",1))
    db.execute("""INSERT INTO study_outcomes
                  (id,study_id,participant_id,outcome_name,value,unit,observation_type,timepoint,session_id,recorded_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
               ("outcome-e2e",study,participant,"resilience_score",82.0,"points","TRAINING","POST",None,now()))

    claims_before=db.one("SELECT COUNT(*) AS n FROM claims WHERE project_id=?",(project["id"],))["n"]
    result=OutcomeFeedbackService(db).propose_research_from_study(
        study,"resilience_score","TRAINING","researcher")
    assert result["scientific_status"]=="CANDIDATE_ONLY"
    assert result["finding"]["status"]=="CANDIDATE"
    assert result["research_proposal"]["trigger_type"]=="OUTCOME_FEEDBACK"
    assert result["research_proposal"]["status"]=="PROPOSED"
    assert db.one("SELECT COUNT(*) AS n FROM claims WHERE project_id=?",(project["id"],))["n"]==claims_before
