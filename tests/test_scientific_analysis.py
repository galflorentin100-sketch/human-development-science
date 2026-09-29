import json
from app.database import Database
from app.scientific_analysis import ScientificAnalysisEngine

def setup(tmp_path):
    db=Database(str(tmp_path/"analysis.db")); db.migrate()
    db.execute("INSERT INTO companies VALUES ('c','HDS','m','v','p','2026')")
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES ('a','Researcher','researcher','m','[]','[]','1','IDLE','2026')")
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES ('p','c','test','RUNNING','a','2026')")
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at,protocol_hash) VALUES ('s','study','RCT','adults','', '2026','protocol-test-hash')")
    analysis_spec=json.dumps({"outcome_name":"score","registered_outcome_name":"score","estimand":"between-arm change difference","population":"randomized participants","estimator":"unadjusted","ci_method":"normal_approximation_95","missing_data_policy":"complete cases","multiplicity_policy":"primary only","subgroup_policy":"none","stopping_rule":"fixed","baseline_timepoint":"baseline","post_timepoint":"post","retention_timepoint":"retention","allowed_methods":["RANDOMIZED_ARM","INFERENTIAL_RANDOMIZED_ARM","LONGITUDINAL_RETENTION","DESCRIPTIVE"]})
    db.execute("INSERT INTO study_analysis_plans(id,study_id,version,analysis_spec,frozen,frozen_at,created_at) VALUES (?,?,?,?,?,?,?)",("plan","s",1,analysis_spec,1,"2026","2026"))
    for pid,arm in [('i','INTERVENTION'),('c1','CONTROL')]:
        db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(pid,'s',pid,'CONSENTED','2026'))
        db.execute("INSERT INTO study_assignments(id,study_id,participant_id,arm,assigned_at,method) VALUES (?,?,?,?,?,?)",(pid+'a','s',pid,arm,'2026','random_choice'))
    return db

def test_randomized_arm_analysis_is_unadjusted_between_arm_change(tmp_path):
    db=setup(tmp_path)
    for pid,base,post,ret in [('i',10,16,15),('c1',10,12,11)]:
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'b','s',pid,'score',base,'TRAINING','2026-01'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'p','s',pid,'score',post,'TRAINING','2026-02'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'r','s',pid,'score',ret,'RETENTION','2026-03'))
    out=ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','score')
    metrics={x['metric_name']:x['metric_value'] for x in out['metrics']}
    assert metrics['intervention_mean_change']==6
    assert metrics['control_mean_change']==2
    assert metrics['between_arm_change_difference']==4
    assert metrics['retention_intervention_mean']==15
    assert metrics['retention_control_mean']==11
    assert 'no confidence interval' in out['result']['uncertainty']

def test_randomized_analysis_requires_frozen_plan(tmp_path):
    db=setup(tmp_path)
    db.execute("UPDATE study_analysis_plans SET frozen=0 WHERE id='plan'")
    try:
        ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','score')
        assert False
    except ValueError as exc:
        assert 'frozen' in str(exc)


def test_analysis_rejects_unregistered_outcome(tmp_path):
    db=setup(tmp_path)
    try:
        ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','different_outcome')
        assert False
    except ValueError as exc:
        assert "preregistered outcome" in str(exc)


def test_analysis_rejects_tampered_frozen_plan_hash(tmp_path):
    db=setup(tmp_path)
    db.execute("UPDATE study_analysis_plans SET analysis_spec=? WHERE id='plan'",
               (json.dumps({"spec":json.dumps({"outcome_name":"score","allowed_methods":["RANDOMIZED_ARM"]}),"sha256":"tampered"}),))
    try:
        ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','score')
        assert False
    except ValueError as exc:
        assert "integrity hash" in str(exc)


def test_randomized_analysis_records_protocol_plan_and_dataset_audit(tmp_path):
    db=setup(tmp_path)
    for pid,base,post in [('i',10,16),('c1',10,12)]:
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'b','s',pid,'score',base,'TRAINING','2026-01'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'p','s',pid,'score',post,'TRAINING','2026-02'))
    out=ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','score')
    audit=ScientificAnalysisEngine(db).analysis_audit('s','plan','score')
    assert len(audit)==1
    assert audit[0]["method"]=="RANDOMIZED_ARM"
    assert audit[0]["protocol_hash"]=="protocol-test-hash"
    assert audit[0]["dataset_hash"]
    assert audit[0]["analysis_plan_hash"]


def test_randomized_analysis_records_protocol_plan_and_dataset_audit(tmp_path):
    db=setup(tmp_path)
    for pid,base,post in [('i',10,16),('c1',10,12)]:
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'b','s',pid,'score',base,'TRAINING','2026-01'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'p','s',pid,'score',post,'TRAINING','2026-02'))
    ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','score')
    audit=ScientificAnalysisEngine(db).analysis_audit('s','plan','score')
    assert len(audit)==1
    assert audit[0]["method"]=="RANDOMIZED_ARM"
    assert audit[0]["protocol_hash"]=="protocol-test-hash"
    assert audit[0]["dataset_hash"]
    assert audit[0]["analysis_plan_hash"]
