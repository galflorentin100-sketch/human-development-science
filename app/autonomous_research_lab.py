"""Continuous, governed autonomous research lab.

The lab can independently discover and execute low-risk digital research work
without requiring founder approval for every cycle. Scientific admission,
human-participant work, publication, spending, and other high-risk actions still
pass the existing governance gates.
"""
import json
from uuid import uuid4
from app.models import now
from app.research_engine import ResearchEngine
from app.research_agent import ResearchAgentService
from app.orchestrator import CompanyOrchestrator


class AutonomousResearchLab:
    def __init__(self, db):
        self.db = db
        self._ensure()

    def _ensure(self):
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS autonomous_lab_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                question TEXT NOT NULL,
                workspace_id TEXT,
                task_id TEXT,
                status TEXT NOT NULL,
                outcome TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT
            )"""
        )
        self.db.execute(
            """CREATE INDEX IF NOT EXISTS idx_autonomous_lab_runs_project
               ON autonomous_lab_runs(project_id, started_at DESC)"""
        )

    def _project(self, project_id):
        project = self.db.one("SELECT * FROM projects WHERE id=?", (project_id,))
        if not project:
            raise ValueError("project not found")
        if project["status"] not in {"ACTIVE", "RUNNING"}:
            raise ValueError("project is not executable")
        return project

    def discover(self, project_id, limit=10):
        """Generate research work candidates from the project's unresolved questions."""
        self._project(project_id)
        if not 1 <= int(limit) <= 50:
            raise ValueError("limit must be 1..50")

        questions = self.db.all(
            """SELECT id,question,status,created_at
               FROM research_questions
               WHERE project_id=? AND status NOT IN ('RESOLVED','CLOSED')
               ORDER BY created_at ASC LIMIT ?""",
            (project_id, int(limit)),
        )
        candidates = []
        for row in questions:
            candidates.append({
                "source": "research_question",
                "source_id": row["id"],
                "question": row["question"],
                "reason": "open research question",
            })

        # Self-audit findings become research candidates rather than silently
        # mutating scientific state.
        try:
            from app.self_audit import SelfAuditEngine
            audit = SelfAuditEngine(self.db).run()
            for finding in audit.get("findings", []):
                entity_project = finding.get("project_id")
                if entity_project and str(entity_project) != str(project_id):
                    continue
                candidates.append({
                    "source": "self_audit",
                    "source_id": finding.get("entity_id"),
                    "question": finding["message"],
                    "reason": finding["kind"],
                })
        except Exception:
            # Discovery must remain available even when an optional audit
            # subsystem is temporarily unavailable; execution gates still apply.
            pass

        deduped = []
        seen = set()
        for item in candidates:
            key=(item["source"], str(item["source_id"]), item["question"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return {
            "project_id": project_id,
            "candidate_count": len(deduped),
            "candidates": deduped,
            "autonomous": True,
            "policy": "digital research may proceed without per-cycle founder approval; scientific state changes remain gated",
        }

    def _workspace_for(self, project_id, question):
        row = self.db.one(
            """SELECT * FROM research_workspaces
               WHERE project_id=? AND question=?
                 AND status IN ('DRAFT','ACTIVE','SYNTHESIS_READY','REVIEWED')
               ORDER BY created_at DESC LIMIT 1""",
            (project_id, question),
        )
        if row:
            return row
        ws = ResearchEngine(self.db).create(
            project_id, question, scope="Autonomous HDS digital research", owner="autonomous-research-lab"
        )
        return ResearchEngine(self.db).activate(ws["id"], "autonomous-research-lab")

    def run_once(self, project_id, question=None):
        """Start one bounded digital research task and execute it through normal gates."""
        self._project(project_id)
        if question is None:
            discovered = self.discover(project_id, 1)["candidates"]
            if not discovered:
                return {"status": "NO_RESEARCH_CANDIDATE", "project_id": project_id}
            question = discovered[0]["question"]
        if not str(question or "").strip():
            raise ValueError("research question is required")

        workspace = self._workspace_for(project_id, str(question).strip())
        task_info = ResearchAgentService(self.db).create_task(
            workspace["id"], owner="autonomous-research-lab"
        )
        run_id = str(uuid4())
        started = now()
        self.db.execute(
            """INSERT INTO autonomous_lab_runs
               (id,project_id,question,workspace_id,task_id,status,started_at)
               VALUES (?,?,?,?,?,?,?)""",
            (run_id, project_id, question.strip(), workspace["id"], task_info["task"]["id"],
             "RUNNING", started),
        )

        result = CompanyOrchestrator(self.db).execute_next(project_id)
        status = result.get("status", "UNKNOWN")
        terminal = status in {
            "COMPLETED", "EXECUTION_FAILED", "EXECUTION_PREFLIGHT_FAILED",
            "RETRY_SCHEDULED", "FAILED", "WAITING_FOR_APPROVAL",
            "WAITING_FOR_OUTPUT_REVIEW", "NO_EXECUTABLE_TASK",
        }
        final_status = status if terminal else "RUNNING"
        self.db.execute(
            """UPDATE autonomous_lab_runs
               SET status=?, outcome=?, error=?, completed_at=?
               WHERE id=?""",
            (
                final_status,
                json.dumps(result, default=str, sort_keys=True),
                result.get("error"),
                now() if terminal else None,
                run_id,
            ),
        )
        return {
            "status": final_status,
            "run_id": run_id,
            "workspace_id": workspace["id"],
            "task_id": task_info["task"]["id"],
            "result": result,
        }

    def run_continuously(self, project_id, cycles=10):
        """Run bounded autonomous research cycles; an external scheduler can call this repeatedly."""
        self._project(project_id)
        cycles = int(cycles)
        if not 1 <= cycles <= 100:
            raise ValueError("cycles must be 1..100")
        history = []
        for _ in range(cycles):
            item = self.run_once(project_id)
            history.append(item)
            if item["status"] in {"NO_RESEARCH_CANDIDATE", "WAITING_FOR_APPROVAL"}:
                break
        return {
            "project_id": project_id,
            "cycles": len(history),
            "status": history[-1]["status"] if history else "NO_RESEARCH_CANDIDATE",
            "history": history,
            "continuous": True,
            "next_cycle": "Call run_continuously again from the scheduler; no founder prompt is required for digital research.",
        }
