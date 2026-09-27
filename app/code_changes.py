"""Governed code-change lifecycle.

This service stores proposed patches as data. It never executes arbitrary code.
Execution must happen in an external isolated runner after approval.
"""
from uuid import uuid4
from app.models import now


ALLOWED_FORMATS={"UNIFIED_DIFF","FILE_REPLACEMENT"}
RISK_LEVELS={"LOW","MEDIUM","HIGH","CRITICAL"}
STATUSES={"PROPOSED","APPROVAL_PENDING","APPROVED","VERIFIED","REJECTED","ROLLED_BACK"}


class CodeChangeService:
    def __init__(self,db):
        self.db=db

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

    def mark_verified(self, proposal_id, verification_run_id, rollback_payload=None):
        if not str(verification_run_id or "").strip(): raise ValueError("verification run is required")
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not row or row["status"]!="APPROVED": raise ValueError("proposal is not approved")
            updated=con.execute("""UPDATE code_change_proposals
                SET status='VERIFIED',verification_run_id=?,rollback_payload=?,updated_at=?
                WHERE id=? AND status='APPROVED'""",
                (verification_run_id,rollback_payload,now(),proposal_id))
            if updated.rowcount!=1: raise ValueError("proposal changed concurrently")
        return self.get(proposal_id)

    def rollback(self, proposal_id, actor):
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not row or row["status"]!="VERIFIED": raise ValueError("only verified changes can be rolled back")
            if not row["rollback_payload"]: raise ValueError("rollback payload is missing")
            updated=con.execute("""UPDATE code_change_proposals
                SET status='ROLLED_BACK',updated_at=? WHERE id=? AND status='VERIFIED'""",(now(),proposal_id))
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
