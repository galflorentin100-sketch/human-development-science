"""Governed scheduler for low-risk autonomous digital research.

This layer may start bounded literature/research-agent work without per-cycle
founder approval. It never authorizes participant research, interventions,
publication, spending, or external contact.
"""
import json
from uuid import uuid4
from app.models import now
from app.autonomous_research import AutonomousResearchPlanner
from app.research_queue import ResearchQueue
from app.research_agent import ResearchAgentService

class AutonomousResearchScheduler:
    DIGITAL_ONLY = "DIGITAL_RESEARCH"

    def __init__(self, db):
        self.db = db

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS autonomous_research_runs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            queue_item_id TEXT,
            workspace_id TEXT,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

    def _eligible(self, candidate):
        return candidate.get("kind") in {"RESEARCH", "SCIENTIFIC_MAINTENANCE"}

    def schedule_once(self, project_id, actor="autonomous-research"):
        self._ensure()
        project=self.db.one("SELECT * FROM projects WHERE id=?",(project_id,))
        if not project:
            raise ValueError("project not found")
        if project["status"] not in {"ACTIVE","RUNNING"}:
            return {"status":"PROJECT_NOT_EXECUTABLE","project_status":project["status"]}

        plan=AutonomousResearchPlanner(self.db).next_work()
        candidate=next((x for x in plan["next"] if self._eligible(x)), None)
        if not candidate:
            return {"status":"NO_ELIGIBLE_DIGITAL_RESEARCH","candidate_count":plan["candidate_count"]}

        question=str(candidate["title"]).strip()
        queue=ResearchQueue(self.db)
        item=queue.propose(
            project_id, question,
            rationale="Autonomous low-risk digital research selected by evidence-gap/risk policy.",
            trigger_type="AUTONOMOUS_SCHEDULER",
            priority="HIGH" if candidate["priority"] >= 90 else "NORMAL",
        )
        item_id=item["id"]

        # Autonomous execution is permitted only for the explicit digital mode.
        if candidate.get("kind") not in {"RESEARCH","SCIENTIFIC_MAINTENANCE"}:
            raise ValueError("autonomous execution policy permits digital research only")

        with self.db.transaction() as con:
            ts=now()
            workspace=con.execute(
                "SELECT * FROM research_workspaces WHERE project_id=? AND question=? AND status IN ('DRAFT','ACTIVE','SYNTHESIS_READY','REVIEWED') LIMIT 1",
                (project_id,question)).fetchone()
            if workspace:
                workspace=dict(workspace)
            else:
                wid=str(uuid4())
                con.execute(
                    "INSERT INTO research_workspaces(id,project_id,question,scope,inclusion_rules,exclusion_rules,status,owner,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (wid,project_id,question,
                     "Autonomous bounded digital research. No participants, intervention, publication, spending, or external contact.",
                     "[]","[]","ACTIVE",actor,ts,ts))
                workspace=dict(con.execute("SELECT * FROM research_workspaces WHERE id=?",(wid,)).fetchone())
            con.execute(
                "UPDATE research_workspaces SET research_queue_id=?,updated_at=? WHERE id=?",
                (item_id,ts,workspace["id"]))
            con.execute(
                "UPDATE hds_research_queue SET research_queue_workspace_id=?,status='IN_PROGRESS',updated_at=? WHERE id=? AND status='PROPOSED'",
                (workspace["id"],ts,item_id))
            run_id=str(uuid4())
            con.execute(
                "INSERT INTO autonomous_research_runs(id,project_id,queue_item_id,workspace_id,mode,status,reason,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (run_id,project_id,item_id,workspace["id"],self.DIGITAL_ONLY,"STARTED",
                 "Autonomous digital research; governed gates remain in force.",ts,ts))
        task=ResearchAgentService(self.db).create_task(workspace["id"],owner=actor)
        self.db.execute("UPDATE autonomous_research_runs SET status='TASK_CREATED',updated_at=? WHERE id=?",(now(),run_id))
        return {"status":"TASK_CREATED","run_id":run_id,"queue_item_id":item_id,
                "workspace_id":workspace["id"],"task":task["task"],"candidate":candidate}

    def run(self, project_id, cycles=1):
        if not 1 <= int(cycles) <= 25:
            raise ValueError("cycles must be 1..25")
        results=[]
        for _ in range(int(cycles)):
            result=self.schedule_once(project_id)
            results.append(result)
            if result["status"] != "TASK_CREATED":
                break
        return {"status":"COMPLETED","cycles":len(results),"results":results}
