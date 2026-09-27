import uuid

from app.database import Database
from app.models import now
from app.continuous_improvement import ContinuousImprovementService


def _setup(db, verified=0):
    company, agent, project, source, claim, evidence = [str(uuid.uuid4()) for _ in range(6)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(company,"c","m","v","truth",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(agent,"a","researcher","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(project,company,"o","ACTIVE",agent,now()))
    db.execute("INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(source,"Paper","https://example.org/"+source,"Author",2025,"PAPER",now(),"test"))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,project,"test","INFERENCE","VERIFIED",0.8,"SUPPORTED",now()))
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_by,created_at) VALUES (?,?,?,?,?,?,?,?)",(evidence,claim,source,"SUPPORTS","excerpt",verified,"test",now()))
    if verified:
        db.execute("INSERT INTO evidence_reviews(id,evidence_id,reviewer,verdict,rationale,created_at) VALUES (?,?,?,?,?,?)",(str(uuid.uuid4()),evidence,"reviewer","VERIFIED","verified in test",now()))
    return project, evidence


def test_science_improvement_requires_existing_verified_evidence(tmp_path):
    db=Database(str(tmp_path/"improvement.db"))
    _, evidence=_setup(db, verified=0)
    svc=ContinuousImprovementService(db)
    try:
        svc.propose("Test","SCIENCE","hypothesis","metric","owner",evidence)
        assert False, "unverified scientific evidence must be rejected at proposal time"
    except ValueError as exc:
        assert "independently verified" in str(exc)


def test_science_improvement_accepts_verified_evidence(tmp_path):
    db=Database(str(tmp_path/"improvement_verified.db"))
    _, evidence=_setup(db, verified=1)
    svc=ContinuousImprovementService(db)
    proposal=svc.propose("Test","SCIENCE","hypothesis","metric","owner",evidence)
    started=svc.start_experiment(proposal["id"],"design","baseline","owner")
    assert started["status"]=="EXPERIMENT"
    result=svc.record_result(proposal["id"],"SUPPORTED","result",evidence)
    assert result["status"]=="EXPERIMENT"
    adopted=svc.adopt(proposal["id"],"founder","rationale")
    assert adopted["status"]=="ADOPTED"
