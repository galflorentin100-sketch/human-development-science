"""Governed replication planning for completed scientific experiments.

Replication proposals are digital research records only. They do not authorize
participant recruitment, intervention, spending, publication, or external contact.
"""
import json
from uuid import uuid4
from app.models import now

class ReplicationEngine:
    STATUSES={"PROPOSED","READY","COMPLETED","ABORTED"}

    def __init__(self,db):
        self.db=db
        self.db.execute("""CREATE TABLE IF NOT EXISTS hds_replication_proposals (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            source_experiment_id TEXT NOT NULL,
            replication_question TEXT NOT NULL,
            rationale TEXT NOT NULL,
            design_constraints TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            result TEXT,
            interpretation TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

    def propose(self,project_id,source_experiment_id,rationale,design_constraints=()):
        exp=self.db.one("SELECT * FROM hds_experiments WHERE id=? AND project_id=?",(source_experiment_id,project_id))
        if not exp: raise ValueError("source experiment not found in project")
        if exp["status"]!="COMPLETED":
            raise ValueError("replication requires a completed source experiment")
        if not str(rationale or "").strip():
            raise ValueError("replication rationale is required")
        constraints=[str(x) for x in (design_constraints or ())]
        question="Replication of: "+str(exp["research_question"]).strip()
        i=str(uuid4()); ts=now()
        self.db.execute(
            """INSERT INTO hds_replication_proposals
            (id,project_id,source_experiment_id,replication_question,rationale,design_constraints,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (i,project_id,source_experiment_id,question,rationale.strip(),
             json.dumps(constraints,sort_keys=True),"PROPOSED",ts,ts))
        return self.get(i)

    def get(self,proposal_id):
        return self.db.one("SELECT * FROM hds_replication_proposals WHERE id=?",(proposal_id,))

    def ready(self,proposal_id):
        row=self.get(proposal_id)
        if not row or row["status"]!="PROPOSED":
            raise ValueError("replication proposal must be PROPOSED")
        with self.db.transaction() as con:
            updated=con.execute("UPDATE hds_replication_proposals SET status='READY',updated_at=? WHERE id=? AND status='PROPOSED'",(now(),proposal_id))
            if updated.rowcount!=1: raise ValueError("replication proposal changed concurrently")
        return self.get(proposal_id)

    def record_result(self,proposal_id,result,interpretation=""):
        row=self.get(proposal_id)
        if not row or row["status"]!="READY":
            raise ValueError("replication proposal must be READY")
        if not str(result or "").strip():
            raise ValueError("replication result is required")
        with self.db.transaction() as con:
            updated=con.execute(
                "UPDATE hds_replication_proposals SET status='COMPLETED',result=?,interpretation=?,updated_at=? WHERE id=? AND status='READY'",
                (result.strip(),str(interpretation or "").strip(),now(),proposal_id))
            if updated.rowcount!=1: raise ValueError("replication proposal changed concurrently")
        return self.get(proposal_id)

    def abort(self,proposal_id,reason):
        if not str(reason or "").strip(): raise ValueError("abort reason is required")
        row=self.get(proposal_id)
        if not row or row["status"] not in {"PROPOSED","READY"}:
            raise ValueError("replication proposal cannot be aborted")
        with self.db.transaction() as con:
            updated=con.execute(
                "UPDATE hds_replication_proposals SET status='ABORTED',result=?,updated_at=? WHERE id=? AND status IN ('PROPOSED','READY')",
                ("ABORTED: "+reason.strip(),now(),proposal_id))
            if updated.rowcount!=1: raise ValueError("replication proposal changed concurrently")
        return self.get(proposal_id)

    def list(self,project_id,status=None):
        if status and status not in self.STATUSES: raise ValueError("invalid replication status")
        q="SELECT * FROM hds_replication_proposals WHERE project_id=?"
        args=[project_id]
        if status: q+=" AND status=?"; args.append(status)
        return self.db.all(q+" ORDER BY created_at DESC",tuple(args))
