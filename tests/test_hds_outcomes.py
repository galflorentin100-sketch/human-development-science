from app.database import Database
from app.hds_outcomes import HDSOutcomeService


def test_hds_outcome_requires_preregistered_measure_and_consent(tmp_path):
    db=Database(str(tmp_path/"outcomes.db"))
    db.migrate()
    from uuid import uuid4
    from app.models import now

    project=str(uuid4()); study=str(uuid4()); participant=str(uuid4()); measure=str(uuid4()); binding=str(uuid4())
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES ('hds','HDS','m','v','truth',?)",(now(),))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(project,"hds","outcome test","RUNNING","chief-scientist",now()))
    db.execute("INSERT INTO studies(id,title,design,findings,created_at) VALUES (?,?,?,?,?)",(study,"Outcome Study","pilot","",now()))
    # studies are legacy rows without project_id in the base schema; add it for project-scoped behavior.
    try:
        db.execute("UPDATE studies SET project_id=? WHERE id=?",(project,study))
    except Exception:
        pass
    db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(participant,study,"p1","PENDING",now()))
    db.execute("INSERT INTO study_measure_definitions(id,study_id,name,operational_definition,method,scale_type,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(measure,study,"run_time","time to complete","timed test","CONTINUOUS","PREREGISTERED",now()))
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
