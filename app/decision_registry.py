"""Traceable organizational decisions for HDS.

Decisions are organizational records, not scientific facts.
They preserve rationale, evidence, assumptions, expected outcomes and later outcomes.
"""
from datetime import datetime, timezone
import uuid

STATUSES={"OPEN","REVIEWED","RETIRED"}

def _now():
    return datetime.now(timezone.utc).isoformat()

class DecisionRegistry:
    def __init__(self, db):
        self.db=db

    def create(self, decision, rationale, alternatives, evidence, assumptions, expected_outcome, created_by, review_at=None):
        values=(decision,rationale,alternatives,evidence,assumptions,expected_outcome,created_by)
        if not all(str(v).strip() for v in values):
            raise ValueError("decision, rationale, alternatives, evidence, assumptions, expected_outcome and created_by are required")
        ident=str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO organizational_decisions
            (id,decision,rationale,alternatives,evidence,assumptions,expected_outcome,review_at,status,created_by,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (ident,decision,rationale,alternatives,evidence,assumptions,expected_outcome,review_at,"OPEN",created_by,_now()),
        )
        return self.get(ident)

    def record_outcome(self, decision_id, outcome):
        self._require(decision_id)
        if not str(outcome).strip():
            raise ValueError("outcome is required")
        self.db.execute("UPDATE organizational_decisions SET outcome=?,status='REVIEWED',updated_at=? WHERE id=?",(outcome,_now(),decision_id))
        return self.get(decision_id)

    def retire(self, decision_id, rationale):
        self._require(decision_id)
        if not str(rationale).strip():
            raise ValueError("retirement rationale is required")
        self.db.execute("UPDATE organizational_decisions SET status='RETIRED',outcome=?,updated_at=? WHERE id=?",(rationale,_now(),decision_id))
        return self.get(decision_id)

    def get(self, decision_id):
        return self._require(decision_id)

    def list(self, status=None):
        if status is not None and status not in STATUSES:
            raise ValueError("invalid decision status")
        if status:
            return self.db.all("SELECT * FROM organizational_decisions WHERE status=? ORDER BY created_at DESC",(status,))
        return self.db.all("SELECT * FROM organizational_decisions ORDER BY created_at DESC")

    def _require(self, decision_id):
        row=self.db.one("SELECT * FROM organizational_decisions WHERE id=?",(decision_id,))
        if not row:
            raise ValueError("decision not found")
        return row
