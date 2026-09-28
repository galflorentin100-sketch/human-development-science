"""Governed code-change lifecycle.

This service stores proposed patches as data. It never executes arbitrary code.
Execution must happen in an external isolated runner after approval.
"""
from uuid import uuid4
import hashlib
from app.models import now


ALLOWED_FORMATS={"UNIFIED_DIFF","FILE_REPLACEMENT"}
RISK_LEVELS={"LOW","MEDIUM","HIGH","CRITICAL"}
STATUSES={"PROPOSED","APPROVAL_PENDING","APPROVED","VERIFIED","DEPLOYED","REJECTED","ROLLED_BACK"}
RUN_TYPES={"VERIFICATION","DEPLOYMENT","ROLLBACK"}


class CodeChangeService:
    def __init__(self,db):
        self.db=db

    @staticmethod
    def fingerprint(proposal):
        payload={
            "project_id":str(proposal["project_id"]),
            "maintenance_work_id":str(proposal["maintenance_work_id"]),
            "title":str(proposal["title"]),
            "patch_format":str(proposal["patch_format"]),
            "patch_payload":str(proposal["patch_payload"]),
            "test_command":str(proposal["test_command"]),
            "risk_level":str(proposal["risk_level"]),
        }
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()

    def propose(self, project_id, maintenance_work_id, title, patch_format, patch_payload, test_command, risk_level, actor):
        if patch_format not in ALLOWED_FORMATS: raise ValueError("unsupported patch format")
        if risk_level not in RISK_LEVELS: raise ValueError("invalid risk level")
        if not all(str(x or "").strip() for x in (title,patch_payload,test_command,actor)):
            raise ValueError("title, patch, test command, and actor are required")
        work=self.db.one("SELECT * FROM maintenance_work WHERE id=?",(maintenance_work_id,))
        if not work: raise ValueError("maintenance work not found")
        if work["status"] not in {"PROPOSED","APPROVAL_PENDING","APPROVED"}:
            raise ValueError("maintenance work is not changeable")
        entity_project_map = {
            "project": ("projects", "id"),
            "claim": ("claims", "id"),
            "evidence": ("evidence", "id"),
            "research_finding": ("research_findings", "id"),
            "training_protocol": ("training_protocols", "id"),
            "intervention": ("interventions", "id"),
            "experiment": ("hds_experiments", "id"),
            "study": ("studies", "id"),
            "research_workspace": ("research_workspaces", "id"),
        }
        mapping = entity_project_map.get(work["entity_type"])
        if not mapping:
            raise ValueError("maintenance work is not project-scoped")
        table, key = mapping
        if work["entity_type"] == "project":
            resource = self.db.one(f"SELECT id FROM {table} WHERE {key}=?", (work["entity_id"],))
            resource_project_id = resource["id"] if resource else None
        else:
            resource = self.db.one(f"SELECT project_id FROM {table} WHERE {key}=?", (work["entity_id"],))
            resource_project_id = resource.get("project_id") if resource else None
        if not resource_project_id:
            raise ValueError("maintenance resource not found")
        if str(resource_project_id) != str(project_id):
            raise ValueError("maintenance work belongs to another project")
        i=str(uuid4())
        self.db.execute("""INSERT INTO code_change_proposals
            (id,project_id,maintenance_work_id,title,patch_format,patch_payload,test_command,
             risk_level,status,proposed_by,approved_by,verification_run_id,rollback_payload,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (i,project_id,maintenance_work_id,title,patch_format,patch_payload,test_command,
             risk_level,"PROPOSED",actor,None,None,None,now(),now()))
        return self.get(i)

    def approve(self, proposal_id, actor):
        if not str(actor or "").strip(): raise ValueError("actor is required")
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not row or row["status"]!="PROPOSED": raise ValueError("proposal is not awaiting approval")
            if str(row["proposed_by"])==str(actor): raise ValueError("separation of duties required")
            updated=con.execute("""UPDATE code_change_proposals
                SET status='APPROVED',approved_by=?,updated_at=? WHERE id=? AND status='PROPOSED'""",
                (actor,now(),proposal_id))
            if updated.rowcount!=1: raise ValueError("proposal changed concurrently")
        return self.get(proposal_id)

    def record_verification(self, proposal_id, verification_run_id, passed, return_code=None, timed_out=False, output=""):
        if not str(verification_run_id or "").strip(): raise ValueError("verification run is required")
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not row or row["status"]!="APPROVED": raise ValueError("proposal is not approved")
            if con.execute("SELECT 1 FROM code_change_verifications WHERE verification_run_id=?",(verification_run_id,)).fetchone():
                raise ValueError("verification run already recorded")
            digest=hashlib.sha256(str(output or "").encode("utf-8")).hexdigest()
            con.execute("""INSERT INTO code_change_verifications
                (id,proposal_id,verification_run_id,passed,return_code,timed_out,output_digest,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (str(uuid4()),proposal_id,verification_run_id,1 if passed else 0,return_code,1 if timed_out else 0,digest,now()))
        return self.db.one("SELECT * FROM code_change_verifications WHERE verification_run_id=?",(verification_run_id,))

    def mark_verified(self, proposal_id, verification_run_id, rollback_payload=None):
        if not str(verification_run_id or "").strip(): raise ValueError("verification run is required")
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not row or row["status"]!="APPROVED": raise ValueError("proposal is not approved")
            run=con.execute(
                "SELECT * FROM code_change_execution_runs WHERE id=? AND proposal_id=? AND run_type='VERIFICATION'",
                (verification_run_id,proposal_id),
            ).fetchone()
            if not run or run["status"]!="PASSED":
                raise ValueError("verification run is not a recorded successful runner result")
            if str(run["proposal_fingerprint"])!=self.fingerprint(dict(row)):
                raise ValueError("verification result does not match the current proposal")
            updated=con.execute("""UPDATE code_change_proposals
                SET status='VERIFIED',verification_run_id=?,rollback_payload=?,updated_at=?
                WHERE id=? AND status='APPROVED'""",
                (verification_run_id,rollback_payload,now(),proposal_id))
            if updated.rowcount!=1: raise ValueError("proposal changed concurrently")
        return self.get(proposal_id)

    def record_deployed(self, proposal_id, deployment_run_id, actor):
        if not str(actor or "").strip(): raise ValueError("actor is required")
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not row or row["status"]!="VERIFIED": raise ValueError("only verified changes can be deployed")
            run=con.execute(
                "SELECT * FROM code_change_execution_runs WHERE id=? AND proposal_id=? AND run_type='DEPLOYMENT'",
                (deployment_run_id,proposal_id),
            ).fetchone()
            if not run or run["status"]!="PASSED":
                raise ValueError("deployment run is not a recorded successful deployment")
            if str(run["proposal_fingerprint"])!=self.fingerprint(dict(row)):
                raise ValueError("deployment result does not match the current proposal")
            updated=con.execute(
                "UPDATE code_change_proposals SET status='DEPLOYED',updated_at=? WHERE id=? AND status='VERIFIED'",
                (now(),proposal_id),
            )
            if updated.rowcount!=1: raise ValueError("proposal changed concurrently")
        return self.get(proposal_id)

    def rollback(self, proposal_id, rollback_run_id, actor):
        if not str(actor or "").strip(): raise ValueError("actor is required")
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not row or row["status"]!="DEPLOYED": raise ValueError("only deployed changes can be rolled back")
            if not row["rollback_payload"]: raise ValueError("rollback payload is missing")
            run=con.execute(
                "SELECT * FROM code_change_execution_runs WHERE id=? AND proposal_id=? AND run_type='ROLLBACK'",
                (rollback_run_id,proposal_id),
            ).fetchone()
            if not run or run["status"]!="PASSED":
                raise ValueError("rollback run is not a recorded successful rollback")
            if str(run["proposal_fingerprint"])!=self.fingerprint(dict(row)):
                raise ValueError("rollback result does not match the deployed proposal")
            updated=con.execute(
                "UPDATE code_change_proposals SET status='ROLLED_BACK',updated_at=? WHERE id=? AND status='DEPLOYED'",
                (now(),proposal_id),
            )
            if updated.rowcount!=1: raise ValueError("proposal changed concurrently")
        return self.get(proposal_id)

    def reject(self, proposal_id, actor):
        with self.db.transaction() as con:
            updated=con.execute("""UPDATE code_change_proposals
                SET status='REJECTED',updated_at=? WHERE id=? AND status IN ('PROPOSED','APPROVAL_PENDING')""",(now(),proposal_id))
            if updated.rowcount!=1: raise ValueError("proposal is not rejectable")
        return self.get(proposal_id)

    def get(self, proposal_id):
        row=self.db.one("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,))
        if not row: raise ValueError("code change proposal not found")
        return row
