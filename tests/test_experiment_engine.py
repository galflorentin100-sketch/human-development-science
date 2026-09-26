import uuid
from app.database import Database
from app.workflow import ResearchCycle

def setup(db):
    from app.models import now
    c,a,p=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(c,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(a,"a","researcher","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(p,c,"o","ACTIVE",a,now()))
    return p

def test_experiment_result_requires_verified_evidence(tmp_path):
    from app.experiment_engine import ExperimentEngine
    db=Database(str(tmp_path/"exp.db")); ResearchCycle(db); pid=setup(db)
    exp=ExperimentEngine(db).create(pid,"Question","Hypothesis","RCT","population","intervention","comparison","outcome",'{"primary":"outcome"}')
    ExperimentEngine(db).preregister(exp["id"]); from app.experiment_safety import ExperimentSafetyReviewer; ExperimentSafetyReviewer(db).review(exp["id"],"ACCEPT","safe to execute","founder"); ExperimentEngine(db).start(exp["id"])
    try:
        ExperimentEngine(db).record_result(exp["id"],"observed","descriptive",["missing"])
        assert False
    except ValueError as exc:
        assert "verified evidence" in str(exc)

def test_experiment_analysis_stays_descriptive(tmp_path):
    from app.experiment_engine import ExperimentEngine
    from app.experiment_analyzer import ExperimentAnalyzer
    from app.evidence_pipeline import EvidencePipeline
    from app.models import now
    db=Database(str(tmp_path/"analysis.db")); ResearchCycle(db); pid=setup(db)
    exp=ExperimentEngine(db).create(pid,"Question","Hypothesis","RCT","population","intervention","comparison","outcome",'{"primary":"outcome"}')
    ExperimentEngine(db).preregister(exp["id"]); from app.experiment_safety import ExperimentSafetyReviewer; ExperimentSafetyReviewer(db).review(exp["id"],"ACCEPT","safe to execute","founder"); ExperimentEngine(db).start(exp["id"])
    source=EvidencePipeline(db).register_source("Paper","https://example.org","Author",2025)
    claim=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,status,classification,confidence,review_required,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",(claim,pid,"claim","SUPPORTED","INFERENCE",1.0,0,now(),now()))
    EvidencePipeline(db).ingest_text(source["id"],"excerpt")
    ev=EvidencePipeline(db).attach(claim,source["id"],"excerpt","SUPPORTS",actor="researcher")
    EvidencePipeline(db).review(ev["id"],"founder","VERIFIED","verified")
    result=ExperimentEngine(db).record_result(exp["id"],"observed change","descriptive interpretation",[ev["id"]])
    analysis=ExperimentAnalyzer(db).analyze(exp["id"])
    assert analysis["interpretation_type"]=="DESCRIPTIVE"
    assert analysis["causal_claim_supported"] is False
    finding=ExperimentAnalyzer(db).candidate_finding(exp["id"],"researcher")
    assert finding["status"]=="CANDIDATE"


def test_analyzer_exposes_result_status(tmp_path):
    from app.experiment_engine import ExperimentEngine
    from app.experiment_analyzer import ExperimentAnalyzer
    db=Database(str(tmp_path/"status.db")); ResearchCycle(db); pid=setup(db)
    e=ExperimentEngine(db).create(pid,"Question","Hypothesis","RCT","population","intervention","comparison","outcome",'{"primary":"outcome"}')
    ExperimentEngine(db).preregister(e["id"])
    from app.experiment_safety import ExperimentSafetyReviewer
    ExperimentSafetyReviewer(db).review(e["id"],"ACCEPT","safe","founder")
    ExperimentEngine(db).start(e["id"])
    result=ExperimentEngine(db).record_result(e["id"],"observed","descriptive",[])
    assert ExperimentAnalyzer(db).analyze(e["id"])["status"]=="RESULT_AVAILABLE"
