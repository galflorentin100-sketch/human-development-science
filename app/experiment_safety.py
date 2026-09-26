from uuid import uuid4
from app.models import now

class ExperimentSafetyReviewer:
    def __init__(self,db):
        self.db=db
        self.db.execute("CREATE TABLE IF NOT EXISTS experiment_safety_reviews (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(experiment_id))")

    def review(self,experiment_id,decision,rationale,reviewer):
        if decision not in {"ACCEPT","REJECT","NEEDS_REVIEW"}: raise ValueError("invalid safety decision")
        if not str(rationale or "").strip(): raise ValueError("safety rationale is required")
        exp=self.db.one("SELECT id,project_id,status FROM hds_experiments WHERE id=?",(experiment_id,))
        if not exp: raise ValueError("experiment not found")
        if exp["status"] not in {"DRAFT","READY"}: raise ValueError("safety review must occur before experiment execution")
        rid=str(uuid4())
        self.db.execute("INSERT INTO experiment_safety_reviews(id,experiment_id,reviewer,decision,rationale,created_at) VALUES (?,?,?,?,?,?) ON CONFLICT(experiment_id) DO UPDATE SET reviewer=excluded.reviewer,decision=excluded.decision,rationale=excluded.rationale,created_at=excluded.created_at",(rid,experiment_id,reviewer,decision,rationale,now()))
        return self.db.one("SELECT * FROM experiment_safety_reviews WHERE experiment_id=?",(experiment_id,))
