from app.database import Database
from app.scientific_analysis import ScientificAnalysisEngine

def test_missingness_report_separates_missing_from_observed(tmp_path):
    db=Database(str(tmp_path/"m.db")); db.migrate()
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at) VALUES ('s','s','RCT','adults','','2026')")
    for pid in ('p1','p2'):
        db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(pid,'s',pid,'CONSENTED','2026'))
    db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",('o1','s','p1','x',10,'REAL_WORLD','2026'))
    db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at,missing_reason) VALUES (?,?,?,?,?,?,?,?)",('o2','s','p2','x',None,'REAL_WORLD','2026','DROPOUT'))
    out=ScientificAnalysisEngine(db).missingness_report('s','x')
    assert out['REAL_WORLD']['n_observed']==1
    assert out['REAL_WORLD']['n_missing']==1
    assert out['REAL_WORLD']['missing_reasons']['DROPOUT']==1

def test_retention_does_not_impute(tmp_path):
    db=Database(str(tmp_path/"r.db")); db.migrate()
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at) VALUES ('s','s','RCT','adults','','2026')")
    db.execute("INSERT INTO study_analysis_plans(id,study_id,version,analysis_spec,frozen,frozen_at,created_at) VALUES ('p','s',1,'{"allowed_methods":["LONGITUDINAL_RETENTION"]}',1,'2026','2026')")
    for pid in ('p1','p2'):
        db.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(pid,'s',pid,'CONSENTED','2026'))
    db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",('a','s','p1','x',10,'TRAINING','2026-01'))
    db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,outcome_name,value,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?)",('b','s','p1','x',8,'RETENTION','2026-03'))
    out=ScientificAnalysisEngine(db).longitudinal_retention_analysis('s','p','x')
    assert out['n_complete_trajectories']==1
    assert out['post_to_retention_change']['mean']==-2
    assert 'No imputation' in out['missing_data_policy']


def test_freeze_analysis_plan_rejects_incomplete_spec(tmp_path):
    db=Database(str(tmp_path/"f.db")); db.migrate()
    from app.research import ResearchRepository
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at) VALUES ('s','s','RCT','adults','','2026')")
    repo=ResearchRepository(db)
    try:
        repo.freeze_analysis_plan('s','{"outcome_name":"x"}')
        assert False
    except ValueError as exc:
        assert 'missing required fields' in str(exc)
