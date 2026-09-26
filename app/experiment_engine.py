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
        self.db.execute("""CREATE TABLE IF NOT EXISTS hds_experiment_results (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            interpretation TEXT NOT NULL,
            evidence_refs TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        )""")
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
        updated=self.db.execute("UPDATE hds_experiments SET status='READY', preregistered=1, updated_at=? WHERE id=? AND status='DRAFT'",(now(),experiment_id))
        if getattr(updated,"rowcount",1)!=1: raise ValueError("experiment state changed concurrently")
        return self.get(experiment_id)

    def start(self, experiment_id):
        row = self.get(experiment_id)
        if not row or row["status"] != "READY":
            raise ValueError("experiment must be preregistered and READY")
        safety=self.db.one("SELECT decision FROM experiment_safety_reviews WHERE experiment_id=?",(experiment_id,))
        if not safety or safety["decision"]!="ACCEPT":
            raise ValueError("experiment requires an accepted safety review before start")
        updated=self.db.execute("UPDATE hds_experiments SET status='RUNNING', updated_at=? WHERE id=? AND status='READY'",(now(),experiment_id))
        if getattr(updated,"rowcount",1)!=1: raise ValueError("experiment state changed concurrently")
        return self.get(experiment_id)

    def record_result(self, experiment_id, outcome, interpretation, evidence_refs=()):
        row=self.get(experiment_id)
        if not row:
            raise ValueError("experiment not found")
        if row["status"] not in {"RUNNING","COMPLETED"}:
            raise ValueError("experiment result requires a RUNNING or COMPLETED experiment")
        if not str(outcome or "").strip() or not str(interpretation or "").strip():
            raise ValueError("outcome and interpretation are required")
        refs=list(evidence_refs)
        for ref in refs:
            ev=self.db.one("SELECT id,verified FROM evidence WHERE id=?",(str(ref),))
            if not ev or not ev["verified"]:
                raise ValueError("experiment result evidence must reference verified evidence")
        if self.db.one("SELECT id FROM hds_experiment_results WHERE experiment_id=?",(experiment_id,)):
            raise ValueError("experiment already has a result")
        i=str(uuid4())
        self.db.execute(
            "INSERT INTO hds_experiment_results(id,experiment_id,outcome,interpretation,evidence_refs,created_at) VALUES (?,?,?,?,?,?)",
            (i,experiment_id,outcome,interpretation,json.dumps(list(evidence_refs),sort_keys=True),now()),
        )
        from app.knowledge_graph import KnowledgeDependencyGraph
        KnowledgeDependencyGraph(self.db).sync_project(row["project_id"])
        return self.db.one("SELECT * FROM hds_experiment_results WHERE id=?",(i,))

    def result(self, experiment_id):
        return self.db.one("SELECT * FROM hds_experiment_results WHERE experiment_id=?",(experiment_id,))

    def complete(self, experiment_id):
        row = self.get(experiment_id)
        if not row or row["status"] != "RUNNING":
            raise ValueError("experiment must be RUNNING")
        if not self.db.one("SELECT id FROM hds_experiment_results WHERE experiment_id=?",(experiment_id,)):
            raise ValueError("experiment cannot be completed without a recorded result")
        self.db.execute(
            "UPDATE hds_experiments SET status='COMPLETED', updated_at=? WHERE id=?",
            (now(), experiment_id),
        )
        from app.knowledge_graph import KnowledgeDependencyGraph
        KnowledgeDependencyGraph(self.db).sync_project(row["project_id"])
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
