from __future__ import annotations
from dataclasses import dataclass
import json
from uuid import uuid4
from app.database import Database
from app.models import CompanyMessage,now
from app.permissions import Permission,PermissionService
from app.providers import ModelProvider,LocalProvider,ModelRequest,ObservableProvider
@dataclass(frozen=True)
class ExecutionResult:
    message:CompanyMessage; verified:bool; cost_metadata:dict; error:str|None=None
class AgentExecutor:
    def __init__(self,db:Database,provider:ModelProvider|None=None,permissions:PermissionService|None=None):
        self.db=db; self.permissions=permissions or PermissionService(db)
        base=provider or LocalProvider()
        self.provider=ObservableProvider(base,db)
    def execute(self,agent_id,task_id,task_input,context,required_permission=Permission.EXECUTE):
        self.permissions.check(agent_id,required_permission,"task:"+task_id)
        task=self.db.one("SELECT required_permissions FROM tasks WHERE id=?",(task_id,))
        if task is None: raise ValueError("task does not exist")
        for p in json.loads(task["required_permissions"] or "[]"): self.permissions.check(agent_id,Permission(p),"task:"+task_id)
        run_id=str(uuid4()); started=now()
        try:
            response=self.provider.complete(ModelRequest("agent-task",json.dumps({"input":task_input,"context":context}),"local-safe",str(uuid4())))
            message=CompanyMessage.create(agent_id,"coo","task_result",task_id,{"result":response.content},0.0,[],["Model output is unverified."],["Verify evidence before use."])
            status="COMPLETED"; error=None; verified=False
            cost={"provider":response.provider,"model":response.model,"input_tokens":response.input_tokens,"output_tokens":response.output_tokens,"estimated_cost":response.estimated_cost}
        except Exception as exc:
            message=CompanyMessage.create(agent_id,"coo","task_error",task_id,{},0.0,[],[str(exc)],["Retry or escalate."]); status="FAILED"; error=str(exc); verified=False; cost={}
        self.db.execute("INSERT INTO agent_runs(id,agent_id,task_id,status,input_payload,output_payload,started_at,completed_at,confidence,evidence_refs,uncertainties,cost_metadata,error,verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(run_id,agent_id,task_id,status,json.dumps({"input":task_input,"context":context}),json.dumps(message.to_dict()),started,now(),0.0,"[]",json.dumps(message.uncertainties),json.dumps(cost),error,int(verified)))
        self.db.audit("agent.execution","agent_run",run_id,agent_id,{"task_id":task_id,"success":error is None},now(),str(uuid4()))
        return ExecutionResult(message,verified,cost,error)
