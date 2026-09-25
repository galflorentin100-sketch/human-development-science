from app.database import Database
from app.scientific_analysis import ScientificAnalysisEngine

def setup(tmp_path):
    db=Database(str(tmp_path/"analysis.db")); db.migrate()
    db.execute("INSERT INTO companies VALUES ('c','HDS','m','v','p','2026')")
    db.execute("INSERT INTO agents VALUES ('a','Researcher','researcher','m','[]','[]','1','IDLE','2026')")
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES ('p','c','test','RUNNING','a','2026')")
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at) VALUES ('s','study','RCT','adults','', '2026')")
    db.execute("INSERT INTO study_analysis_plans(id,study_id,version,analysis_spec,frozen,frozen_at,created_at) VALUES ('plan','s',1,'preregistered',1,'2026','2026')")
    for pid,arm in [('i','INTERVENTION'),('c1','CONTROL')]:
        db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(pid,'s',pid,'CONSENTED','2026'))
        db.execute("INSERT INTO study_assignments(id,study_id,participant_id,arm,assigned_at,method) VALUES (?,?,?,?,?,?)",(pid+'a','s',pid,arm,'2026','random_choice'))
    return db

def test_inferential_analysis_reports_ci_and_effect_size(tmp_path):
    db=setup(tmp_path)
    values={'i':(10,16),'c1':(10,12)}
    for pid,(base,post) in values.items():
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'b','s',pid,'score',base,'TRAINING','2026-01'))
        db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",(pid+'p','s',pid,'score',post,'TRAINING','2026-02'))
    out=ScientificAnalysisEngine(db).inferential_randomized_arm_analysis('s','plan','score')
    assert out['between_arm_difference']==4
    assert 'cohens_d' in out
    assert out['intervention']['ci95_low'] is None
    assert out['control']['ci95_low'] is None
    assert 'no missing-data model' in out['limitations']

def test_inferential_requires_frozen_plan(tmp_path):
    db=setup(tmp_path); db.execute("UPDATE study_analysis_plans SET frozen=0 WHERE id='plan'")
    try:
        ScientificAnalysisEngine(db).inferential_randomized_arm_analysis('s','plan','score')
        assert False
    except ValueError as exc:
        assert 'frozen' in str(exc)
