from __future__ import annotations

import json
from uuid import uuid4

from app.database import Database
from app.models import now


class CompanyState:
    def __init__(self, db: Database):
        self.db = db

    def snapshot(self) -> dict:
        return {
            "company": self.db.one("SELECT * FROM companies WHERE id='hds'"),
            "goals": self.db.all("SELECT * FROM goals WHERE status='ACTIVE'"),
            "active_projects": self.db.all("SELECT * FROM projects WHERE status IN ('RUNNING','PLANNED')"),
            "active_tasks": self.db.all("SELECT * FROM tasks WHERE status IN ('PLANNED','ASSIGNED','RUNNING','BLOCKED')"),
            "agents": self.db.all("SELECT id,name,role,status,version,manager FROM agents"),
            "risks": self.db.all("SELECT * FROM risks WHERE status='OPEN'"),
            "opportunities": self.db.all("SELECT * FROM opportunities WHERE status='OPEN'"),
            "experiments": self.db.all("SELECT * FROM experiments WHERE status!='COMPLETED'"),
            "decisions": self.db.all("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 10"),
            "failures": self.db.all("SELECT * FROM failures ORDER BY created_at DESC LIMIT 10"),
            "lessons": self.db.all("SELECT * FROM lessons ORDER BY created_at DESC LIMIT 10"),
            "approvals": self.db.all("SELECT * FROM approvals WHERE status='PENDING'"),
        }

    def decision(self, decision: str, owner: str, alternatives: list[str], evidence: list[str], assumptions: list[str], confidence: float, expected_outcome: str, follow_up: str | None = None) -> dict:
        decision_id = str(uuid4())
        self.db.execute("INSERT INTO decisions VALUES (?, 'hds', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)", (decision_id, decision, json.dumps(alternatives), json.dumps(evidence), json.dumps(assumptions), confidence, expected_outcome, owner, follow_up, now()))
        self._audit("decision.recorded", "decision", decision_id, owner, {"decision": decision})
        return self.db.one("SELECT * FROM decisions WHERE id=?", (decision_id,))

    def failure(self, stage: str, expected: str, actual: str, root_cause: str, lesson: str, owner: str = "system", contributing: list[str] | None = None, corrective_action: str | None = None) -> dict:
        failure_id = str(uuid4())
        self.db.execute("INSERT INTO failures (id,project_id,stage,expected_result,actual_result,root_cause,lesson,created_at,contributing_factors,corrective_action,owner) VALUES (?,NULL,?,?,?,?,?,?,?, ?,?)", (failure_id, stage, expected, actual, root_cause, lesson, now(), json.dumps(contributing or []), corrective_action, owner))
        self.db.execute("INSERT INTO lessons VALUES (?, 'hds', ?, ?, ?)", (str(uuid4()), lesson, failure_id, now()))
        self._audit("failure.recorded", "failure", failure_id, owner, {"root_cause": root_cause})
        return self.db.one("SELECT * FROM failures WHERE id=?", (failure_id,))

    def _audit(self, event: str, entity_type: str, entity_id: str, actor: str, payload: dict) -> None:
        self.db.audit(event, entity_type, entity_id, actor, payload, now(), str(uuid4()))
