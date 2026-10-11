from __future__ import annotations
from dataclasses import dataclass
import json
from uuid import uuid4
from app.database import Database
from app.models import CompanyMessage,now
from app.permissions import Permission,PermissionService
from app.providers import ModelProvider,LocalProvider,ModelRequest,ObservableProvider,configured_provider
from app.cost_controls import CostControl
@dataclass(frozen=True)
class ExecutionResult:
    message:CompanyMessage; verified:bool; cost_metadata:dict; error:str|None=None
def build_agent_prompt(task, task_input, context):
    """Build an explicit evidence-bounded prompt for scientific researcher tasks."""
    raw_criteria = task.get("success_criteria") if hasattr(task, "get") else None
    try:
        criteria = json.loads(raw_criteria or "{}")
    except (TypeError, ValueError):
        criteria = {}
    title = str(task.get("title") or "") if hasattr(task, "get") else ""
    if not title.startswith("[RESEARCH]") or not isinstance(criteria, dict) or "source_packet" not in criteria:
        return json.dumps({"input": task_input, "context": context}, sort_keys=True)

    research_input = {
        "question": criteria.get("question") or title.removeprefix("[RESEARCH]").strip(),
        "scope": criteria.get("scope"),
        "inclusion_rules": criteria.get("inclusion_rules", []),
        "exclusion_rules": criteria.get("exclusion_rules", []),
        "source_packet": criteria.get("source_packet", []),
        "required_output": criteria.get("required_output", {}),
    }
    return (
        "You are the HDS scientific literature research agent. Perform only the bounded "
        "digital research described in INPUT_JSON. Use ONLY the supplied source_packet; "
        "do not browse or claim to have searched any additional source. Source records are "
        "discovery-only and unverified. Never invent studies, authors, quotations, methods, "
        "sample sizes, statistics, findings, or source IDs.\n"
        "Return ONLY one valid JSON object with keys candidate_claims, result, limitations, "
        "uncertainty. candidate_claims must be a list of objects with statement, classification "
        "(FACT, INFERENCE, HYPOTHESIS, or OPINION), source_id, exact_excerpt, and stance "
        "(SUPPORTS, CONTRADICTS, or NEUTRAL). Every exact_excerpt must be copied verbatim as a "
        "substring of that source's supplied abstract. Every source_id must exactly match a "
        "source_packet item. FACT means the source explicitly reports the statement, not that "
        "the claim has been independently verified. Do not label an inference as a fact. If "
        "the source packet has no usable abstracts or cannot support a claim, return an empty "
        "candidate_claims list and clearly state the limitation. Do not say independent review "
        "has happened. Keep contradictions and uncertainty explicit.\n"
        "INPUT_JSON:\n" + json.dumps(research_input, ensure_ascii=False, sort_keys=True)
    )


class AgentExecutor:
    def __init__(self,db:Database,provider:ModelProvider|None=None,permissions:PermissionService|None=None):
        self.db=db; self.permissions=permissions or PermissionService(db); self.provider=ObservableProvider(provider or configured_provider(),db); self.costs=CostControl(db)
    def execute(self,agent_id,task_id,task_input,context,required_permission=Permission.EXECUTE,claimed=False):
        self.permissions.check(agent_id,required_permission,"task:"+task_id)
        task=self.db.one("SELECT * FROM tasks WHERE id=?",(task_id,))
        if task is None: raise ValueError("task does not exist")
        if str(task["assigned_agent_id"]) != str(agent_id):
            raise PermissionError("agent is not assigned to this task")
        task_project_id=str(task["project_id"])
        context_project_id=str((context or {}).get("project_id") or "")
        if context_project_id != task_project_id:
            raise PermissionError("execution project does not match task project")
        high_risk={"PUBLISH","SPEND","DEPLOY","DELETE","CONTACT_EXTERNAL_PARTY"}
        action=task_input.get("action") if isinstance(task_input,dict) else None
        approval_id=task_input.get("approval_id") if isinstance(task_input,dict) else None
        if action in high_risk:
            from app.approvals import ApprovalService, ApprovalRequired
            if not approval_id:
                raise ApprovalRequired(f"approval required for {action}")
            project_id=(context or {}).get("project_id")
            ApprovalService(self.db).consume(
                approval_id,
                expected_action=action,
                expected_context={"task_id":task_id,"project_id":project_id},
                actor=agent_id,
            )
        for p in json.loads(task["required_permissions"] or "[]"): self.permissions.check(agent_id,Permission(p),"task:"+task_id)
        if task["status"] in ("COMPLETED","CANCELLED"):
            return ExecutionResult(CompanyMessage.create(agent_id,"coo","task_result",task_id,{"result":"already terminal"},0.0,[],[],[]),True,{},None)
        if claimed:
            if task["status"] != "RUNNING":
                raise RuntimeError("claimed task is not RUNNING")
        else:
            with self.db.transaction() as con:
                claimed_row=con.execute("UPDATE tasks SET status='RUNNING',updated_at=? WHERE id=? AND status IN ('PLANNED','ASSIGNED')",(now(),task_id))
                if getattr(claimed_row, "rowcount", 1) != 1:
                    raise RuntimeError("task claim lost")
        run_id=str(uuid4()); started=now(); error=None
        try:
            correlation_id=str(uuid4())
            request=ModelRequest("agent-task",build_agent_prompt(task,task_input,context),"research-safe" if str(task["title"]).startswith("[RESEARCH]") else "local-safe",correlation_id)
            preflight_cost=self.provider.preflight(request)
            if preflight_cost > 0:
                self.costs.reserve(correlation_id,preflight_cost,"preflight","estimated","agent-task",agent_id,metadata={"task_id":task_id})
            response=self.provider.complete(request)
            if preflight_cost > 0:
                self.costs.settle(correlation_id,float(response.estimated_cost or 0),response.provider,response.model,"agent-task",agent_id,metadata={"task_id":task_id,"preflight_cost":preflight_cost})
            elif response.estimated_cost and response.estimated_cost > 0:
                self.costs.record(correlation_id,response.estimated_cost,response.provider,response.model,"agent-task",agent_id,metadata={"task_id":task_id,"preflight_cost":preflight_cost})
            message=CompanyMessage.create(agent_id,"coo","task_result",task_id,{"result":response.content},0.0,[],["Model output is unverified."],["Verify evidence before use."])
            cost={"provider":response.provider,"model":response.model,"input_tokens":response.input_tokens,"output_tokens":response.output_tokens,"estimated_cost":response.estimated_cost}
        except Exception as exc:
            error=str(exc)
            try:
                if "correlation_id" in locals() and preflight_cost > 0:
                    self.costs.release(correlation_id)
            except Exception:
                pass
            message=CompanyMessage.create(agent_id,"coo","task_error",task_id,{},0.0,[],[error],["Retry or escalate."]); cost={}
        status="FAILED" if error else "REVIEW"
        ts=now()
        with self.db.transaction() as con:
            con.execute("INSERT INTO agent_runs(id,agent_id,task_id,status,input_payload,output_payload,started_at,completed_at,confidence,evidence_refs,uncertainties,cost_metadata,error,verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id,agent_id,task_id,status,json.dumps({"input":task_input,"context":context}),json.dumps(message.to_dict()),started,ts,0.0,"[]",json.dumps(message.uncertainties),json.dumps(cost),error,0))
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"agent.execution","agent_run",run_id,agent_id,json.dumps({"task_id":task_id,"success":error is None,"verified":False},sort_keys=True),ts))
            updated=con.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=? AND status='RUNNING'",("FAILED" if error else "REVIEW",ts,task_id))
            if updated.rowcount != 1:
                raise RuntimeError("task state changed during execution")
        return ExecutionResult(message,False,cost,error)
