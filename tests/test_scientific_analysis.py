import json
from app.database import Database
from app.scientific_analysis import ScientificAnalysisEngine

def setup(tmp_path):
    db=Database(str(tmp_path/"analysis.db")); db.migrate()
    db.execute("INSERT INTO companies VALUES ('c','HDS','m','v','p','2026')")
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES ('a','Researcher','researcher','m','[]','[]','1','IDLE','2026')")
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES ('p','c','test','RUNNING','a','2026')")
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at,protocol_hash,status) VALUES ('s','study','RCT','adults','', '2026','protocol-test-hash','COMPLETED')")
    analysis_spec=json.dumps({"spec":{"outcome_name":"score","registered_outcome_name":"score","estimand":"between-arm change difference","population":"randomized participants","estimator":"unadjusted","ci_method":"normal_approximation_95","missing_data_policy":"complete cases","multiplicity_policy":"primary only","subgroup_policy":"none","stopping_rule":"fixed","baseline_timepoint":"baseline","post_timepoint":"post","retention_timepoint":"retention","allowed_methods":["RANDOMIZED_ARM","INFERENTIAL_RANDOMIZED_ARM","LONGITUDINAL_RETENTION","DESCRIPTIVE"]}})
    db.execute("INSERT INTO study_analysis_plans(id,study_id,version,analysis_spec,frozen,frozen_at,created_at) VALUES (?,?,?,?,?,?,?)",("plan","s",1,analysis_spec,1,"2026","2026"))
    for pid,arm in [('i','INTERVENTION'),('c1','CONTROL')]:
        db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(pid,'s',pid,'CONSENTED','2026'))
        db.execute("INSERT INTO study_assignments(id,study_id,participant_id,arm,assigned_at,method) VALUES (?,?,?,?,?,?)",(pid+'a','s',pid,arm,'2026','random_choice'))
    return db

def test_randomized_arm_analysis_is_unadjusted_between_arm_change(tmp_path):
    db=setup(tmp_path)
    for pid,base,post,ret in [('i',10,16,15),('c1',10,12,11)]:
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'b','s',pid,'score',base,'TRAINING','baseline','2026-01'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'p','s',pid,'score',post,'TRAINING','post','2026-02'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'r','s',pid,'score',ret,'RETENTION','retention','2026-03'))
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
    import pytest
    with pytest.raises(Exception, match="immutable"):
        db.execute("UPDATE study_analysis_plans SET frozen=0 WHERE id='plan'")


def test_analysis_rejects_unregistered_outcome(tmp_path):
    db=setup(tmp_path)
    try:
        ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','different_outcome')
        assert False
    except ValueError as exc:
        assert "preregistered outcome" in str(exc)


def test_analysis_rejects_tampered_frozen_plan_hash(tmp_path):
    db=setup(tmp_path)
    import pytest
    with pytest.raises(Exception, match="immutable"):
        db.execute("UPDATE study_analysis_plans SET analysis_spec=? WHERE id='plan'",
                   (json.dumps({"spec":json.dumps({"outcome_name":"score","allowed_methods":["RANDOMIZED_ARM"]}),"sha256":"tampered"}),))


def test_randomized_analysis_records_protocol_plan_and_dataset_audit(tmp_path):
    db=setup(tmp_path)
    for pid,base,post in [('i',10,16),('c1',10,12)]:
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'b','s',pid,'score',base,'TRAINING','baseline','2026-01'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'p','s',pid,'score',post,'TRAINING','post','2026-02'))
    out=ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','score')
    audit=ScientificAnalysisEngine(db).analysis_audit('s','plan','score')
    assert len(audit)==1
    assert audit[0]["method"]=="RANDOMIZED_ARM"
    assert audit[0]["protocol_hash"]=="protocol-test-hash"
    assert audit[0]["dataset_hash"]
    assert audit[0]["analysis_plan_hash"]




def test_analysis_audit_hashes_canonical_spec_and_dataset_includes_assignment(tmp_path):
    db=setup(tmp_path)
    for pid,base,post in [('i',10,16),('c1',10,12)]:
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'b','s',pid,'score',base,'TRAINING','baseline','2026-01'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'p','s',pid,'score',post,'TRAINING','post','2026-02'))
    engine=ScientificAnalysisEngine(db)
    engine.randomized_arm_analysis('s','plan','score')
    audit=db.one("SELECT * FROM study_analysis_audit WHERE study_id='s'")
    spec=db.one("SELECT analysis_spec FROM study_analysis_plans WHERE id='plan'")["analysis_spec"]
    payload=json.loads(spec)
    assert audit["analysis_plan_hash"] == __import__("hashlib").sha256(json.dumps(payload["spec"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
    before=audit["dataset_hash"]
    db.execute("UPDATE study_assignments SET arm='CONTROL' WHERE participant_id='i' AND study_id='s'")
    assert engine._dataset_hash('s','score') != before



def test_analysis_result_rolls_back_if_audit_fails(tmp_path, monkeypatch):
    db=setup(tmp_path)
    for pid,base,post in [('i',10,16),('c1',10,12)]:
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'b','s',pid,'score',base,'TRAINING','baseline','2026-01'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,timepoint,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(pid+'p','s',pid,'score',post,'TRAINING','post','2026-02'))
    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit failure")
    monkeypatch.setattr(ScientificAnalysisEngine, "_record_analysis_audit", fail_audit)
    try:
        ScientificAnalysisEngine(db).randomized_arm_analysis('s','plan','score')
        assert False
    except RuntimeError as exc:
        assert str(exc) == "audit failure"
    assert db.one("SELECT COUNT(*) AS n FROM study_analysis_results WHERE study_id='s'")["n"] == 0
    assert db.one("SELECT COUNT(*) AS n FROM study_analysis_metrics WHERE study_id='s'")["n"] == 0



def test_analysis_audit_has_one_record_per_result(tmp_path):
    db=setup(tmp_path)
    audit_id="audit-1"
    db.execute(
        "INSERT INTO study_analysis_results(id,study_id,analysis_plan_id,outcome_name,n_total,n_observed,estimate,uncertainty,missing_data_note,interpretation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("result-1","s","plan","score",2,2,4.0,"u","m","i","2026"),
    )
    db.execute(
        "INSERT INTO study_analysis_audit(id,study_id,analysis_plan_id,analysis_result_id,protocol_hash,analysis_plan_hash,dataset_hash,method,population_note,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (audit_id,"s","plan","result-1","p","a","d","DESCRIPTIVE","population","2026"),
    )
    try:
        db.execute(
            "INSERT INTO study_analysis_audit(id,study_id,analysis_plan_id,analysis_result_id,protocol_hash,analysis_plan_hash,dataset_hash,method,population_note,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("audit-2","s","plan","result-1","p2","a2","d2","DESCRIPTIVE","population","2026"),
        )
        assert False
    except Exception:
        pass
    assert db.one("SELECT COUNT(*) AS n FROM study_analysis_audit WHERE analysis_result_id='result-1'")["n"] == 1


def test_analysis_plan_blocks_unplanned_multiplicity_and_requires_explicit_controls(tmp_path):
    db=setup(tmp_path)
    engine=ScientificAnalysisEngine(db)
    plan=db.one("SELECT * FROM study_analysis_plans WHERE id='plan'")
    assert engine.validate_analysis_spec(plan)["valid"]
    db.execute("INSERT INTO study_analysis_results(id,study_id,analysis_plan_id,outcome_name,n_total,n_observed,estimate,uncertainty,missing_data_note,interpretation,created_at) VALUES ('existing','s','plan','score',2,2,1,NULL,NULL,'primary','2026')")
    try:
        engine.randomized_arm_analysis("s","plan","score")
        assert False
    except ValueError as exc:
        assert "primary-only" in str(exc)

    adjusted=dict(json.loads(plan["analysis_spec"]))
    adjusted["multiplicity_policy"]="adjusted"
    adjusted["multiplicity_method"]="holm"
    adjusted["subgroup_policy"]="none"
    adjusted_plan=dict(plan); adjusted_plan["analysis_spec"]=json.dumps(adjusted)
    assert engine.validate_analysis_spec(adjusted_plan)["valid"]

    subgroup=dict(json.loads(plan["analysis_spec"]))
    subgroup["subgroup_policy"]="pre_specified"
    try:
        subgroup_plan=dict(plan); subgroup_plan["analysis_spec"]=json.dumps(subgroup)
        engine.validate_analysis_spec(subgroup_plan)
        assert False
    except ValueError as exc:
        assert "subgroups" in str(exc)


def test_fixed_stopping_requires_completed_study(tmp_path):
    db=setup(tmp_path)
    db.execute("UPDATE studies SET status='RUNNING' WHERE id='s'")
    try:
        ScientificAnalysisEngine(db).randomized_arm_analysis("s","plan","score")
        assert False
    except ValueError as exc:
        assert "fixed stopping rule" in str(exc)


def test_missing_data_policy_is_executable_not_declarative(tmp_path):
    db=setup(tmp_path)
    plan=db.one("SELECT * FROM study_analysis_plans WHERE id='plan'")
    spec=json.loads(plan["analysis_spec"])
    spec["missing_data_policy"]="last observation carried forward"
    bad=dict(plan); bad["analysis_spec"]=json.dumps(spec)
    try:
        ScientificAnalysisEngine(db).validate_analysis_spec(bad)
        assert False
    except ValueError as exc:
        assert "missing-data policy" in str(exc)
