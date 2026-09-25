from app.database import Database
from app.workflow import ResearchCycle
from app.research import StudyExecution
from app.measurement import MeasurementRegistry

def make_db(tmp_path):
    db=Database(str(tmp_path/"measurement.db")); ResearchCycle(db)
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at,status) VALUES (?,?,?,?,?,?,?)",("s","S","RCT","adults","","2026-01-01","APPROVED"))
    return db

def test_measurement_definition_and_binding_are_preregistered(tmp_path):
    db=make_db(tmp_path)
    m=MeasurementRegistry(db).define("s","goal_execution_rate","Completed planned target actions divided by planned target actions","Structured daily log","PROPORTION")
    b=MeasurementRegistry(db).bind("s",m["id"],"TRAINING","baseline")
    assert b["required"]==1
    assert MeasurementRegistry(db).validate_observation("s",m["id"],"TRAINING","baseline")["name"]=="goal_execution_rate"

def test_outcome_requires_preregistered_measurement_when_measure_id_is_used(tmp_path):
    db=make_db(tmp_path)
    p=StudyExecution(db).participant("s","p")
    try:
        StudyExecution(db).outcome("s",p["id"],"goal_execution_rate",0.5,observation_type="TRAINING",measure_id="missing",timepoint="baseline")
        assert False
    except ValueError as exc:
        assert "preregistered" in str(exc) or "belong" in str(exc)

def test_outcome_rejects_wrong_timepoint_binding(tmp_path):
    db=make_db(tmp_path)
    m=MeasurementRegistry(db).define("s","goal_execution_rate","Completed planned target actions divided by planned target actions","Structured daily log","PROPORTION")
    MeasurementRegistry(db).bind("s",m["id"],"TRAINING","baseline")
    p=StudyExecution(db).participant("s","p")
    try:
        StudyExecution(db).outcome("s",p["id"],"goal_execution_rate",0.5,observation_type="TRAINING",measure_id=m["id"],timepoint="post")
        assert False
    except ValueError as exc:
        assert "preregistered" in str(exc)

def test_measurement_registry_rejects_invalid_scale(tmp_path):
    db=make_db(tmp_path)
    try:
        MeasurementRegistry(db).define("s","x","definition","method","MADE_UP")
        assert False
    except ValueError as exc:
        assert "scale type" in str(exc)
