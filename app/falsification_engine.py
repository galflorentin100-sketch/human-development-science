"""Hypothesis challenge and falsification planning.

Creates explicit attempts to challenge hypotheses. It never upgrades or downgrades
scientific truth from the challenge record alone.
"""
import json
from uuid import uuid4
from app.models import now

class FalsificationEngine:
    STATUSES={"PROPOSED","IN_PROGRESS","COMPLETED","ABORTED"}

    def __init__(self,db):
        self.db=db
        self._ensure()

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS hds_falsification_challenges (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            hypothesis_id TEXT NOT NULL,
            challenge TEXT NOT NULL,
            disconfirming_observation TEXT NOT NULL,
            design_constraints TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            result TEXT,
            conclusion TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

    def propose(self,project_id,hypothesis_id,challenge,disconfirming_observation,design_constraints=()):
        hypothesis=self.db.one("SELECT * FROM hypotheses WHERE id=? AND project_id=?",(hypothesis_id,project_id))
        if not hypothesis:
            raise ValueError("hypothesis not found in project")
        if not str(challenge or "").strip() or not str(disconfirming_observation or "").strip():
            raise ValueError("challenge and disconfirming observation are required")
        constraints=[str(x) for x in (design_constraints or ())]
        i=str(uuid4()); ts=now()
        self.db.execute(
            """INSERT INTO hds_falsification_challenges
            (id,project_id,hypothesis_id,challenge,disconfirming_observation,design_constraints,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (i,project_id,hypothesis_id,challenge.strip(),disconfirming_observation.strip(),
             json.dumps(constraints,sort_keys=True),"PROPOSED",ts,ts))
        return self.get(i)

    def get(self,challenge_id):
        return self.db.one("SELECT * FROM hds_falsification_challenges WHERE id=?",(challenge_id,))

    def start(self,challenge_id):
        row=self.get(challenge_id)
        if not row or row["status"]!="PROPOSED":
            raise ValueError("falsification challenge must be PROPOSED")
        # Planning a challenge is digital research. Actual human-participant execution
        # remains outside this engine and must use the existing study/safety gates.
        with self.db.transaction() as con:
            updated=con.execute(
                "UPDATE hds_falsification_challenges SET status='IN_PROGRESS',updated_at=? WHERE id=? AND status='PROPOSED'",
                (now(),challenge_id))
            if updated.rowcount!=1:
                raise ValueError("falsification challenge changed concurrently")
        return self.get(challenge_id)

    def record_result(self,challenge_id,result,conclusion=""):
        row=self.get(challenge_id)
        if not row or row["status"]!="IN_PROGRESS":
            raise ValueError("falsification challenge must be IN_PROGRESS")
        if not str(result or "").strip():
            raise ValueError("falsification result is required")
        with self.db.transaction() as con:
            updated=con.execute(
                "UPDATE hds_falsification_challenges SET status='COMPLETED',result=?,conclusion=?,updated_at=? WHERE id=? AND status='IN_PROGRESS'",
                (result.strip(),str(conclusion or "").strip(),now(),challenge_id))
            if updated.rowcount!=1:
                raise ValueError("falsification challenge changed concurrently")
        return self.get(challenge_id)

    def abort(self,challenge_id,reason):
        if not str(reason or "").strip():
            raise ValueError("abort reason is required")
        row=self.get(challenge_id)
        if not row or row["status"] not in {"PROPOSED","IN_PROGRESS"}:
            raise ValueError("falsification challenge cannot be aborted")
        with self.db.transaction() as con:
            updated=con.execute(
                "UPDATE hds_falsification_challenges SET status='ABORTED',result=?,updated_at=? WHERE id=? AND status IN ('PROPOSED','IN_PROGRESS')",
                ("ABORTED: "+reason.strip(),now(),challenge_id))
            if updated.rowcount!=1:
                raise ValueError("falsification challenge changed concurrently")
        return self.get(challenge_id)

    def list(self,project_id,status=None):
        if status and status not in self.STATUSES:
            raise ValueError("invalid falsification status")
        if status:
            return self.db.all("SELECT * FROM hds_falsification_challenges WHERE project_id=? AND status=? ORDER BY created_at DESC",(project_id,status))
        return self.db.all("SELECT * FROM hds_falsification_challenges WHERE project_id=? ORDER BY created_at DESC",(project_id,))
