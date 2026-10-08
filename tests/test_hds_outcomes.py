from app.database import Database
from app.hds_outcomes import HDSOutcomeService


def test_hds_outcome_requires_preregistered_measure_and_consent(tmp_path):
    db=Database(str(tmp_path/"outcomes.db"))
    from app.workflow import ResearchCycle
    ResearchCycle(db)
    from uuid import uuid4
    from app.models import now

    project=str(uuid4()); study=str(uuid4()); participant=str(uuid4()); measure=str(uuid4()); binding=str(uuid4())
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(project,"hds","outcome test","RUNNING","chief-scientist",now()))
    cols = {row["name"] for row in db.all("PRAGMA table_info(study_measure_definitions)")}
    assert {"reliability_note", "validity_note"} <= cols
    db.execute("INSERT INTO studies(id,title,design,findings,created_at) VALUES (?,?,?,?,?)",(study,"Outcome Study","pilot","",now()))
    # studies are legacy rows without project_id in the base schema; add it for project-scoped behavior.
    try:
        db.execute("UPDATE studies SET project_id=? WHERE id=?",(project,study))
    except Exception:
        pass
    db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(participant,study,"p1","PENDING",now()))
    db.execute("INSERT INTO study_measure_definitions(id,study_id,name,operational_definition,method,scale_type,reliability_note,validity_note,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(measure,study,"run_time","time to complete","timed test","CONTINUOUS","test reliability","test validity","PREREGISTERED",now()))
    db.execute("INSERT INTO study_measure_bindings(id,study_id,measure_id,observation_type,timepoint,required) VALUES (?,?,?,?,?,?)",(binding,study,measure,"REAL_WORLD","POST",1))

    svc=HDSOutcomeService(db)
    try:
        svc.record(study,participant,"run_time",300,"seconds","REAL_WORLD","POST")
        assert False
    except ValueError as exc:
        assert "consent" in str(exc).lower()

    db.execute("UPDATE study_participants SET consent_status='CONSENTED' WHERE id=?",(participant,))
    row=svc.record(study,participant,"run_time",300,"seconds","REAL_WORLD","POST")
    assert row["observation_type"]=="REAL_WORLD"
    assert row["timepoint"]=="POST"


def test_hds_outcome_rejects_unregistered_measure(tmp_path):
    db=Database(str(tmp_path/"unregistered.db"))
    db.migrate()
    from uuid import uuid4
    from app.models import now
    study=str(uuid4()); participant=str(uuid4())
    db.execute("INSERT INTO studies(id,title,design,findings,created_at) VALUES (?,?,?,?,?)",(study,"Study","pilot","",now()))
    db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(participant,study,"p1","CONSENTED",now()))
    try:
        HDSOutcomeService(db).record(study,participant,"invented_measure",1,"x","TRAINING","POST")
        assert False
    except ValueError as exc:
        assert "preregistered" in str(exc)


def test_outcome_feedback_creates_candidate_finding_and_new_research_question(tmp_path):
    db=Database(str(tmp_path/"feedback.db"))
    from app.workflow import ResearchCycle
    ResearchCycle(db)
    from uuid import uuid4
    from app.models import now
    project=str(uuid4()); study=str(uuid4()); participant=str(uuid4()); measure=str(uuid4()); binding=str(uuid4())
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",
               (project,"hds","outcome feedback loop","RUNNING","chief-scientist",now()))
    db.execute("INSERT INTO studies(id,project_id,title,design,findings,created_at) VALUES (?,?,?,?,?,?)",
               (study,project,"Outcome Study","pilot","",now()))
    db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",
               (participant,study,"p1","CONSENTED",now()))
    db.execute("""INSERT INTO study_measure_definitions
        (id,study_id,name,operational_definition,method,scale_type,reliability_note,validity_note,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (measure,study,"transfer_score","score","standardized test","CONTINUOUS",
                "reliability recorded","validity recorded","PREREGISTERED",now()))
    db.execute("""INSERT INTO study_measure_bindings
        (id,study_id,measure_id,observation_type,timepoint,required)
        VALUES (?,?,?,?,?,?)""",
               (binding,study,measure,"NEAR_TRANSFER","POST",1))

    from app.hds_outcomes import HDSOutcomeService
    HDSOutcomeService(db).record(study,participant,"transfer_score",7.5,"points","NEAR_TRANSFER","POST")

    from app.outcome_feedback import OutcomeFeedbackService
    result=OutcomeFeedbackService(db).propose_research_from_study(
        study,"transfer_score","NEAR_TRANSFER","system"
    )
    finding=db.one("SELECT * FROM research_findings WHERE id=?",(result["finding"]["finding_id"],))
    assert finding["status"]=="CANDIDATE"
    assert finding["classification"]=="INFERENCE"
    assert result["research_proposal"]["status"]=="PROPOSED"
    assert result["scientific_status"]=="CANDIDATE_ONLY"
    assert result["research_question"]["status"]=="OPEN"
    assert result["research_question"]["trigger_type"]=="OUTCOME_FEEDBACK"
    assert "observed outcome pattern" in result["research_proposal"]["question"]
