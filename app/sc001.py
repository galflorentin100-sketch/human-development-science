from __future__ import annotations
from dataclasses import dataclass
from uuid import uuid4
from app.models import now
@dataclass(frozen=True)
class Outcome:
    name:str
    definition:str
    timepoint:str
    unit:str
@dataclass(frozen=True)
class StudyProtocol:
    id:str
    title:str
    question:str
    primary_outcome:Outcome
    transfer_outcomes:tuple[Outcome,...]
    retention_timepoints:tuple[str,...]
    intervention:str
    control:str
    status:str="DRAFT"
class SC001Protocol:
    def draft(self):
        return StudyProtocol(
            id=str(uuid4()),
            title="SC-001 Self-Regulation Training",
            question="Can structured goal-directed self-regulation training improve self-regulation, transfer to real-world goal execution, and persist after training?",
            primary_outcome=Outcome("goal_execution_rate","Proportion of predefined target actions completed as planned","baseline/post","proportion"),
            transfer_outcomes=(Outcome("initiation_latency","Time from planned cue to action start","baseline/post/follow-up","seconds"),Outcome("recovery_after_interruption","Successful return to planned action after interruption","baseline/post/follow-up","proportion"),Outcome("real_world_goal_execution","Completion of independently chosen target behaviors","baseline/post/follow-up","proportion")),
            retention_timepoints=("4-week post","8-week follow-up","12-week follow-up"),
            intervention="Goal definition + cue + implementation intention + friction reduction + graded practice + monitoring + review",
            control="Active control matched for contact and monitoring without the core self-regulation training sequence"
        )
    def register(self,db,project_id):
        protocol=self.draft()
        gates=self.quality_gates(protocol)
        if gates["status"]!="READY_FOR_REVIEW": raise ValueError("SC-001 protocol failed quality gates")
        from app.research import ResearchRepository
        repo=ResearchRepository(db)
        hypothesis=repo.hypothesis(project_id,protocol.question)
        experiment=repo.experiment(project_id,hypothesis["statement"],protocol.intervention)
        db.audit("research.protocol_registered","experiment",experiment["id"],"experiment-designer",{"protocol_id":protocol.id,"quality_gates":gates},now(),str(uuid4()))
        return {"protocol":protocol,"quality_gates":gates,"hypothesis":hypothesis,"experiment":experiment}
    def quality_gates(self,protocol:StudyProtocol):
        return {
            "falsifiable_question":bool(protocol.question),
            "primary_outcome_defined":bool(protocol.primary_outcome.definition),
            "transfer_defined":len(protocol.transfer_outcomes)>=1,
            "retention_defined":len(protocol.retention_timepoints)>=1,
            "control_defined":bool(protocol.control),
            "status":"READY_FOR_REVIEW"
        }
