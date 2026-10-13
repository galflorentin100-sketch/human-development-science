"""Governed executors for routed research actions.

Executors only prepare the next bounded task. They do not bypass scientific,
human-participant, publication, spending, or external-contact gates.
"""
import json
from uuid import uuid4
from app.models import now
from app.research_agent import ResearchAgentService

class ResearchActionExecutor:
    def __init__(self,db):
        self.db=db

    def execute(self,workspace_id,action,actor="autonomous-research"):
        ws=self.db.one("SELECT * FROM research_workspaces WHERE id=?",(workspace_id,))
        if not ws: raise ValueError("research workspace not found")
        if ws["status"]!="ACTIVE": raise ValueError("research workspace must be ACTIVE")
        action=str(action or "").upper()
        if action=="INFORMATION_GATHERING":
            result=ResearchAgentService(self.db).create_task(workspace_id,owner=actor)
            return {"status":"TASK_CREATED","action":action,"task":result["task"],"governance":"digital-read-only"}
        if action in {"FALSIFICATION_REVIEW","REPLICATION_REVIEW","EXPERIMENT_DESIGN"}:
            task_id=str(uuid4()); ts=now()
            payload={"action":action,"workspace_id":workspace_id,"question":ws["question"],
                     "governance":"REVIEW_REQUIRED","execution_authorized":False,
                     "rule":"Prepare only; human/safety/scientific gates remain authoritative."}
            with self.db.transaction() as con:
                con.execute(
                    "INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at,owner,required_permissions,retry_limit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (task_id,ws["project_id"],f"[{action}] {ws['question']}","PLANNED",None,2.0,
                     json.dumps(payload,sort_keys=True),ts,ts,actor,json.dumps(["READ"]),0))
            return {"status":"GOVERNED_REVIEW_REQUIRED","action":action,"task":self.db.one("SELECT * FROM tasks WHERE id=?",(task_id,)),"governance":"review-required"}
        raise ValueError("unsupported research action")
