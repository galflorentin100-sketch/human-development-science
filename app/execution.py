from __future__ import annotations
from dataclasses import dataclass
import json
from uuid import uuid4
from app.database import Database
from app.models import CompanyMessage, now
from app.permissions import Permission, PermissionService
from app.providers import ModelProvider, LocalProvider, ModelRequest
@dataclass(frozen=True)
class ExecutionResult:
    message: CompanyMessage; verified: bool; cost_metadata: dict; error: str | None=None
class AgentExecutor:
    def __init__(self,db: Database, provider: ModelProvider | None=None, permissions: PermissionService | None=None): self.db=db; self.provider=provider or LocalProvider(); self.permissions=permissions or PermissionService(db)
    def execute(self, agent_id: str, task_id: str, task_input: dict, context: dict, required_permission: Permission=Permission.EXECUTE) -> ExecutionResult:
        self.permissions.check(agent_id,required_permission,"task:"+task_id)
        task = self.db.one("SELECT required_permissions FROM tasks WHERE id=?", (task_id,))
        if task is None:
            raise ValueError("task does not exist")
        for permission in json.loads(task["required_permissions"]):
            self.permissions.check(agent_id, Permission(permission), "task:" + task_id)
        run_id=str(uuid4()); started=now(); error=None
        try:
            response=self.provider.complete(ModelRequest("agent-task", json.dumps({"input":task_input,"context":context}), "local-safe", str(uuid4())))
            message=CompanyMessage.create(from_agent=agent_id,to_agent="coo",type="task_result",task_id=task_id,payload={"result":response.content},confidence=0.0,evidence_refs=[],uncertainties=["No external model or evidence connector configured."],recommended_actions=["Verify before using output."])
            verified=False; cost={"provider":response.provider,"model":response.model,"input_tokens":response.input_tokens,"output_tokens":response.output_tokens,"estimated_cost":response.estimated_cost}
            status="COMPLETED"
        except Exception as exc:
            error=str(exc); message=CompanyMessage.create(from_agent=agent_id,to_agent="coo",type="task_error",task_id=task_id,payload={},confidence=0.0,evidence_refs=[],uncertainties=[error],recommended_actions=["Escalate or retry."]); verified=False; cost={}; status="FAILED"
        self.db.execute("INSERT INTO agent_runs (id,agent_id,task_id,status,input_payload,output_payload,started_at,completed_at,confidence,evidence_refs,uncertainties,cost_metadata,error,verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",(run_id,agent_id,task_id,status,json.dumps({"input":task_input,"context":context}),json.dumps(message.to_dict()),started,now(),message.confidence,json.dumps(message.evidence_refs),json.dumps(message.uncertainties),json.dumps(cost),error,int(verified)))
        self.db.audit("agent.execution","agent_run",run_id,agent_id,{"task_id":task_id,"success":error is None,"permission":required_permission.value},now(),str(uuid4()))
        return ExecutionResult(message,verified,cost,error)
