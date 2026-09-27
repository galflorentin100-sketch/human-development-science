"""Research-agent orchestration primitives.

The service prepares bounded research tasks and records outputs as unverified
agent work. It never upgrades evidence or findings without the existing gates.
"""
from __future__ import annotations
import json
from app.models import now
from app.tasks import TaskEngine

class ResearchAgentService:
    ROLE="researcher"

    def __init__(self,db):
        self.db=db
        self._ensure()
    
    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS research_agent_tasks (
            task_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, agent_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")

    def create_task(self,workspace_id,agent_id=None,owner="researcher"):
        ws=self.db.one("SELECT * FROM research_workspaces WHERE id=?",(workspace_id,))
        if not ws: raise ValueError("research workspace not found")
        if ws["status"]!="ACTIVE": raise ValueError("research workspace must be ACTIVE")
        agent=agent_id or self._researcher_agent()
        if not agent: raise ValueError("researcher agent not found")
        payload={
            "action":"research","workspace_id":workspace_id,"question":ws["question"],
            "scope":ws["scope"],"inclusion_rules":json.loads(ws["inclusion_rules"] or "[]"),
            "exclusion_rules":json.loads(ws["exclusion_rules"] or "[]"),
            "required_output":{"sources":"source IDs with relevance and provenance","synthesis":"evidence-grounded synthesis","limitations":"known limitations","uncertainty":"explicit uncertainty","evidence_refs":"IDs only for evidence actually used"},
            "guardrails":["Do not invent sources or evidence IDs.","Do not claim causality from descriptive evidence.","Separate evidence from interpretation.","Return insufficient-evidence when support is missing."]
        }
        from uuid import uuid4
        task_id=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at,owner,required_permissions,retry_limit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (task_id,ws["project_id"],f"[RESEARCH] {ws['question']}","PLANNED",agent,2.0,json.dumps(payload,sort_keys=True),ts,ts,owner,json.dumps(["READ"]),1))
            con.execute(
                "INSERT INTO research_agent_tasks(task_id,workspace_id,agent_id,created_at) VALUES (?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET workspace_id=excluded.workspace_id,agent_id=excluded.agent_id,created_at=excluded.created_at",
                (task_id,workspace_id,agent,ts))
        task=self.db.one("SELECT * FROM tasks WHERE id=?",(task_id,))
        return {"task":task,"workspace_id":workspace_id,"agent_id":agent,"input":payload}

    def _researcher_agent(self):
        row=self.db.one("SELECT id FROM agents WHERE status='ACTIVE' AND (id=? OR role=?) ORDER BY created_at LIMIT 1",(self.ROLE,self.ROLE))
        return row["id"] if row else None

    def finalize_review(self,review_id,actor):
        review=self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))
        if not review: raise ValueError("output review not found")
        if review["status"]!="ACCEPTED": raise ValueError("agent output must be ACCEPTED first")
        link=self.db.one("SELECT * FROM research_agent_tasks WHERE task_id=?",(review["task_id"],))
        if not link: raise ValueError("research agent task mapping not found")
        from app.research_engine import ResearchEngine
        payload=json.loads(self.db.one("SELECT output_payload FROM agent_runs WHERE id=?",(review["agent_run_id"],))["output_payload"] or "{}")
        result=payload.get("result") or payload.get("synthesis") or ""
        if isinstance(result,(dict,list)): result=json.dumps(result,sort_keys=True)
        refs=json.loads(review["evidence_refs"] or "[]")
        engine=ResearchEngine(self.db)
        synthesis=engine.synthesize(link["workspace_id"],str(result),
            limitations=str(payload.get("limitations") or ""),
            uncertainty=str(payload.get("uncertainty") or "Agent output was independently evidence-reviewed; interpretation remains bounded."),
            created_by=actor,evidence_refs=refs)
        from app.research_review_pipeline import ResearchReviewPipeline
        review_tasks=ResearchReviewPipeline(self.db).create_for_synthesis(synthesis["id"])
        return {"review":review,"synthesis":synthesis,"workspace_id":link["workspace_id"],"evidence_refs":refs,"review_tasks":review_tasks["tasks"]}
