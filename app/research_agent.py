"""Research-agent orchestration primitives.

The service prepares bounded research tasks and records outputs as unverified
agent work. It never upgrades evidence or findings without the existing gates.
"""
from __future__ import annotations
import json
from uuid import uuid4
from app.tasks import TaskEngine
from app.models import now

class ResearchAgentService:
    ROLE="researcher"

    def __init__(self,db):
        self.db=db

    def create_task(self,workspace_id,agent_id=None,owner="researcher"):
        ws=self.db.one("SELECT * FROM research_workspaces WHERE id=?",(workspace_id,))
        if not ws: raise ValueError("research workspace not found")
        if ws["status"]!="ACTIVE": raise ValueError("research workspace must be ACTIVE")
        agent=agent_id or self._researcher_agent()
        if not agent: raise ValueError("researcher agent not found")
        payload={
            "action":"research",
            "workspace_id":workspace_id,
            "question":ws["question"],
            "scope":ws["scope"],
            "inclusion_rules":json.loads(ws["inclusion_rules"] or "[]"),
            "exclusion_rules":json.loads(ws["exclusion_rules"] or "[]"),
            "required_output":{
                "sources":"source IDs with relevance and provenance",
                "synthesis":"evidence-grounded synthesis",
                "limitations":"known limitations",
                "uncertainty":"explicit uncertainty",
                "evidence_refs":"IDs only for evidence actually used"
            },
            "guardrails":[
                "Do not invent sources or evidence IDs.",
                "Do not claim causality from descriptive evidence.",
                "Separate evidence from interpretation.",
                "Return insufficient-evidence when support is missing."
            ]
        }
        task=TaskEngine(self.db).create_task(
            ws["project_id"],f"[RESEARCH] {ws['question']}",owner,
            ["READ"],agent,metadata={"workspace_id":workspace_id,"agent_role":self.ROLE,"input":payload})
        return {"task":task,"workspace_id":workspace_id,"agent_id":agent,"input":payload}

    def _researcher_agent(self):
        row=self.db.one("SELECT id FROM agents WHERE role=? AND status='ACTIVE' ORDER BY created_at LIMIT 1",(self.ROLE,))
        return row["id"] if row else None
