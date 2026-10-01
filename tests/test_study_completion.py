import json
from app.database import Database
from app.research import StudyExecution


def setup(tmp_path):
    db=Database(str(tmp_path/"completion.db"))
    db.execute("INSERT INTO companies VALUES ('c','HDS','m','v','p','2026')")
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES ('a','Researcher','researcher','m','[]','[]','1','IDLE','2026')")
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES ('p','c','test','RUNNING','a','2026')")
    db.execute(
        "INSERT INTO studies(id,title,design,population,findings,created_at,protocol_hash,status,project_id,protocol_snapshot) "
        "VALUES ('s','study','RCT','adults','','2026','protocol-hash','RUNNING','p','snapshot')"
    )
    spec=json.dumps({
        "outcome_name":"score","estimand":"change","population":"consented participants",
        "estimator":"unadjusted","ci_method":"none",
        "missing_data_policy":"explicit missing reason","multiplicity_policy":"primary only",
        "subgroup_policy":"none","stopping_rule":"fixed","allowed_methods":["DESCRIPTIVE"],
        "baseline_timepoint":"baseline","post_timepoint":"post"
    })
    db.execute(
        "INSERT INTO study_analysis_plans(id,study_id,version,analysis_spec,frozen,frozen_at,created_at) "
        "VALUES ('plan','s',1,?,?,?,?)",
        (json.dumps({"spec":spec,"sha256":"x"}),1,"2026","2026")
    )
    db.execute(
        "INSERT INTO study_measure_definitions(id,study_id,name,operational_definition,method,scale_type,unit,reliability_note,validity_note,status,created_at) "
        "VALUES ('m','s','score','score definition','test','continuous','points','note','note','ACTIVE','2026')"
    )
    db.execute(
        "INSERT INTO study_measure_bindings(id,study_id,measure_id,observation_type,timepoint,required) "
        "VALUES ('b','s','m','TRAINING','baseline',1)"
    )
    for pid in ("p1","p2"):
        db.execute(
            "INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) "
            "VALUES (?,?,?,?,?)",(pid,"s",pid,"CONSENTED","2026")
        )
    return db


def test_complete_requires_each_required_binding_for_each_consented_participant(tmp_path):
    db=setup(tmp_path)
    db.execute(
        "INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) "
        "VALUES ('o1','s','p1','score',10,'TRAINING','baseline','2026')"
    )
    try:
        StudyExecution(db).complete("s")
        assert False
    except ValueError as exc:
        assert "missing required preregistered observations" in str(exc)
    assert db.one("SELECT status FROM studies WHERE id='s'")["status"]=="RUNNING"


def test_complete_accepts_explicit_missing_outcome_reason(tmp_path):
    db=setup(tmp_path)
    db.execute(
        "INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,missing_reason,recorded_at) "
        "VALUES ('o1','s','p1','score',10,'TRAINING','baseline',NULL,'2026')"
    )
    db.execute(
        "INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,missing_reason,recorded_at) "
        "VALUES ('o2','s','p2','score',NULL,'TRAINING','baseline','participant withdrew before measurement','2026')"
    )
    StudyExecution(db).complete("s")
    assert db.one("SELECT status FROM studies WHERE id='s'")["status"]=="COMPLETED"


def test_legacy_mean_change_creates_analysis_audit(tmp_path):
    db=setup(tmp_path)
    db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES ('p1','s','p1','CONSENTED','2026')")
    db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES ('o1','s','p1','score',10,'TRAINING','baseline','2026')")
    db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES ('o2','s','p1','score',12,'TRAINING','post','2026')")
    result=StudyExecution(db).analyze_mean_change("s","plan","score")
    audit=db.one("SELECT * FROM study_analysis_audit WHERE analysis_result_id=?",(result["id"],))
    assert audit is not None
    assert audit["analysis_plan_id"]=="plan"
    assert audit["method"]=="DESCRIPTIVE"
