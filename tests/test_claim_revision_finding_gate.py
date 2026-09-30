from app.claim_revision import ClaimRevisionService
from app.database import Database
import uuid


def _claim(db, project_id):
    cid=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,status,created_at) VALUES (?,?,?,?,?)",
               (cid,project_id,"Existing claim","PROPOSED","2026-01-01T00:00:00Z"))
    return cid


def _finding(db, project_id, status):
    fid=str(uuid.uuid4())
    db.execute("""INSERT INTO research_findings
        (id,project_id,source_type,source_id,statement,classification,status,evidence_refs,interpretation,created_by,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (fid,project_id,"OBSERVATION",None,"Finding","INFERENCE",status,"[]",
         "Descriptive observation only.","researcher","2026-01-01T00:00:00Z"))
    return fid


def test_claim_revision_rejects_candidate_finding(tmp_path):
    db=Database(str(tmp_path/"revision.db"))
    project_id=str(uuid.uuid4())
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",
               (project_id,"hds","test","RUNNING","agent-1","2026-01-01T00:00:00Z"))
    claim_id=_claim(db,project_id)
    finding_id=_finding(db,project_id,"CANDIDATE")

    try:
        ClaimRevisionService(db).propose(
            claim_id,"Updated claim","PROPOSED","rationale",source_finding_id=finding_id)
        assert False, "candidate finding must not inform a claim revision"
    except ValueError as exc:
        assert str(exc)=="source finding must be ACCEPTED before it can inform a claim revision"


def test_claim_revision_accepts_accepted_finding_same_project(tmp_path):
    db=Database(str(tmp_path/"revision_accepted.db"))
    project_id=str(uuid.uuid4())
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",
               (project_id,"hds","test","RUNNING","agent-1","2026-01-01T00:00:00Z"))
    claim_id=_claim(db,project_id)
    finding_id=_finding(db,project_id,"ACCEPTED")

    revision=ClaimRevisionService(db).propose(
        claim_id,"Updated claim","PROPOSED","rationale",source_finding_id=finding_id)

    assert revision["source_finding_id"]==finding_id
    assert revision["status"]=="PROPOSED"
