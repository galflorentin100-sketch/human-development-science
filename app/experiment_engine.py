"""Structured experiment registry with explicit hypotheses and guardrails."""
import json
from uuid import uuid4
from app.models import now

class ExperimentEngine:
    STATUSES = {"DRAFT", "READY", "RUNNING", "COMPLETED", "ABORTED"}

    def __init__(self, db):
        self.db = db
        self._ensure()

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS hds_experiments (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            research_question TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            design TEXT NOT NULL,
            population TEXT NOT NULL,
            intervention TEXT NOT NULL,
            comparison TEXT NOT NULL,
            outcomes TEXT NOT NULL,
            analysis_plan TEXT NOT NULL,
            status TEXT NOT NULL,
            preregistered INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

    def create(self, project_id, research_question, hypothesis, design,
               population, intervention, comparison, outcomes, analysis_plan):
        fields = [project_id, research_question, hypothesis, design, population,
                  intervention, comparison, outcomes, analysis_plan]
        if any(not str(x or "").strip() for x in fields):
            raise ValueError("all experiment design fields are required")
        try:
            parsed = json.loads(analysis_plan)
        except (TypeError, ValueError) as exc:
            raise ValueError("analysis_plan must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("analysis_plan must be an object")
        experiment_id = str(uuid4())
        ts = now()
        self.db.execute(
            """INSERT INTO hds_experiments
            (id,project_id,research_question,hypothesis,design,population,
             intervention,comparison,outcomes,analysis_plan,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,?)""",
            (experiment_id, project_id, research_question, hypothesis, design,
             population, intervention, comparison, outcomes, analysis_plan,
             "DRAFT", ts, ts),
        )
        return self.get(experiment_id)

    def get(self, experiment_id):
        return self.db.one("SELECT * FROM hds_experiments WHERE id=?", (experiment_id,))

    def preregister(self, experiment_id):
        row = self.get(experiment_id)
        if not row:
            raise ValueError("experiment not found")
        if row["status"] != "DRAFT":
            raise ValueError("only DRAFT experiments can be preregistered")
        self.db.execute(
            "UPDATE hds_experiments SET status='READY', preregistered=1, updated_at=? WHERE id=?",
            (now(), experiment_id),
        )
        return self.get(experiment_id)

    def start(self, experiment_id):
        row = self.get(experiment_id)
        if not row or row["status"] != "READY":
            raise ValueError("experiment must be preregistered and READY")
        self.db.execute(
            "UPDATE hds_experiments SET status='RUNNING', updated_at=? WHERE id=?",
            (now(), experiment_id),
        )
        return self.get(experiment_id)

    def complete(self, experiment_id):
        row = self.get(experiment_id)
        if not row or row["status"] != "RUNNING":
            raise ValueError("experiment must be RUNNING")
        self.db.execute(
            "UPDATE hds_experiments SET status='COMPLETED', updated_at=? WHERE id=?",
            (now(), experiment_id),
        )
        return self.get(experiment_id)

    def abort(self, experiment_id, reason):
        if not str(reason or "").strip():
            raise ValueError("abort reason is required")
        row = self.get(experiment_id)
        if not row or row["status"] not in {"READY", "RUNNING"}:
            raise ValueError("experiment cannot be aborted from its current state")
        self.db.execute(
            "UPDATE hds_experiments SET status='ABORTED', updated_at=? WHERE id=?",
            (now(), experiment_id),
        )
        return self.get(experiment_id)

    def list(self, project_id):
        return self.db.all(
            "SELECT * FROM hds_experiments WHERE project_id=? ORDER BY created_at DESC",
            (project_id,),
        )
