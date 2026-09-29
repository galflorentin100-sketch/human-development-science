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


def test_preregistered_outcome_persists_timepoint_and_rejects_duplicate(tmp_path):
    db=make_db(tmp_path)
    m=MeasurementRegistry(db).define("s","goal_execution_rate","Completed planned target actions divided by planned target actions","Structured daily log","PROPORTION")
    MeasurementRegistry(db).bind("s",m["id"],"TRAINING","baseline")
    p=StudyExecution(db).participant("s","p")
    first=StudyExecution(db).outcome("s",p["id"],"goal_execution_rate",0.5,observation_type="TRAINING",measure_id=m["id"],timepoint="baseline")
    assert first["timepoint"]=="baseline"
    try:
        StudyExecution(db).outcome("s",p["id"],"goal_execution_rate",0.6,observation_type="TRAINING",measure_id=m["id"],timepoint="baseline")
        assert False
    except ValueError as exc:
        assert "duplicate" in str(exc)


def test_study_completion_uses_preregistered_observation_types(tmp_path):
    db=make_db(tmp_path)
    db.execute("UPDATE studies SET status='RUNNING',protocol_hash='protocol-hash',protocol_snapshot='snapshot' WHERE id='s'")
    m=MeasurementRegistry(db).define("s","goal_execution_rate","Completed planned target actions divided by planned target actions","Structured daily log","PROPORTION")
    MeasurementRegistry(db).bind("s",m["id"],"TRAINING","baseline")
    p=StudyExecution(db).participant("s","p")
    StudyExecution(db).outcome("s",p["id"],"goal_execution_rate",0.5,observation_type="TRAINING",measure_id=m["id"],timepoint="baseline")
    StudyExecution(db).freeze_analysis_plan("s",'{"outcome_name":"goal_execution_rate","estimand":"descriptive","population":"all","estimator":"mean","ci_method":"none","missing_data_policy":"report","multiplicity_policy":"none","subgroup_policy":"none","stopping_rule":"fixed","allowed_methods":["DESCRIPTIVE"]}')
    completed=StudyExecution(db).complete("s")
    assert completed["status"]=="COMPLETED"


def test_outcome_requires_measure_binding_and_matching_unit(tmp_path):
    db=make_db(tmp_path)
    m=MeasurementRegistry(db).define("s","score","Numeric score","Validated scoring procedure","CONTINUOUS","points")
    MeasurementRegistry(db).bind("s",m["id"],"TRAINING","baseline")
    p=StudyExecution(db).participant("s","p")
    try:
        StudyExecution(db).outcome("s",p["id"],"score",10,observation_type="TRAINING",timepoint="baseline")
        assert False
    except ValueError as exc:
        assert "preregistered measure" in str(exc)
    try:
        StudyExecution(db).outcome("s",p["id"],"score",10,unit="seconds",observation_type="TRAINING",measure_id=m["id"],timepoint="baseline")
        assert False
    except ValueError as exc:
        assert "unit" in str(exc)
