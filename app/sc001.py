from __future__ import annotations
from dataclasses import dataclass, asdict
from uuid import uuid4
import hashlib
import json
from app.approvals import ApprovalService
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
    population:str
    inclusion_criteria:str
    exclusion_criteria:str
    sample_size_target:int
    allocation:str
    analysis_plan:str
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
            control="Active control matched for contact and monitoring without the core self-regulation training sequence",
            population="Adults able to complete the study procedures.",
            inclusion_criteria="Consented adult participant able to complete baseline, post, transfer and follow-up assessments.",
            exclusion_criteria="Any circumstance that prevents informed consent or safe completion of study procedures.",
            sample_size_target=60,
            allocation="Randomized intervention/control allocation.",
            analysis_plan=json.dumps({"outcome_name":"goal_execution_rate","registered_outcome_name":"goal_execution_rate","estimand":"between-arm difference in baseline-to-post change","population":"randomized participants","estimator":"unadjusted change-score difference","ci_method":"normal_approximation_95","missing_data_policy":"complete paired cases; report missingness; no imputation","multiplicity_policy":"primary outcome only for confirmatory interpretation; secondary outcomes descriptive","subgroup_policy":"none unless separately preregistered","stopping_rule":"fixed sample target; no outcome-based stopping","allowed_methods":["INFERENTIAL_RANDOMIZED_ARM","LONGITUDINAL_RETENTION"]},sort_keys=True)
        )
    def register(self,db,project_id):
        protocol=self.draft()
        gates=self.quality_gates(protocol)
        if gates["status"]!="READY_FOR_REVIEW": raise ValueError("SC-001 protocol failed quality gates")
        from app.research import ResearchRepository
        repo=ResearchRepository(db)
        hypothesis=repo.hypothesis(project_id,protocol.question)
        experiment=repo.experiment(project_id,hypothesis["statement"],protocol.intervention)
        study=repo.study(None,protocol.title,"Controlled pilot with baseline/post/follow-up","To be defined","No results recorded; study execution pending.")
        from app.measurement import MeasurementRegistry
        measurements=MeasurementRegistry(db)
        definitions=[]
        for outcome in (protocol.primary_outcome,)+protocol.transfer_outcomes:
            definitions.append(measurements.define(study["id"],outcome.name,outcome.definition,"Predefined behavioral outcome protocol","PROPORTION" if outcome.unit=="proportion" else "DURATION",outcome.unit,"To be established","To be established"))
        for definition in definitions:
            for observation_type,timepoint in (("TRAINING","baseline"),("TRAINING","post"),("REAL_WORLD","follow-up"),("RETENTION","8-week follow-up"),("RETENTION","12-week follow-up")):
                measurements.bind(study["id"],definition["id"],observation_type,timepoint,required=(definition["name"]==protocol.primary_outcome.name or observation_type=="REAL_WORLD"))
        snapshot=json.dumps(asdict(protocol),sort_keys=True)
        digest=hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
        db.execute("INSERT INTO study_protocol_versions(id,study_id,version,snapshot,content_hash,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),study["id"],1,snapshot,digest,now()))
        approval=ApprovalService(db).request(action="SC001:STUDY:"+study["id"],requested_by="study-designer",reason="Founder approval is required before participant data collection or study execution.",risk_level="HIGH",context={"study_id":study["id"],"protocol_id":protocol.id,"protocol_hash":digest},correlation_id=protocol.id)
        db.execute("UPDATE studies SET status=?,protocol_snapshot=?,protocol_hash=?,approval_id=? WHERE id=?",("PENDING_APPROVAL",snapshot,digest,approval["id"],study["id"]))
        db.audit("research.protocol_registered","study",study["id"],"experiment-designer",{"protocol_id":protocol.id,"quality_gates":gates,"protocol_hash":digest,"approval_id":approval["id"]},now(),str(uuid4()))
        return {"protocol":protocol,"quality_gates":gates,"hypothesis":hypothesis,"experiment":experiment,"measurements":definitions,"study":db.one("SELECT * FROM studies WHERE id=?",(study["id"],)),"approval":approval}
    def quality_gates(self,protocol:StudyProtocol):
        import json
        try:
            spec=json.loads(protocol.analysis_plan)
        except (TypeError, ValueError):
            spec={}
        required=("outcome_name","registered_outcome_name","estimand","population","estimator",
                  "ci_method","missing_data_policy","multiplicity_policy","subgroup_policy",
                  "stopping_rule","allowed_methods")
        analysis_contract={k:bool(spec.get(k)) for k in required}
        analysis_contract["allowed_methods_nonempty"]=isinstance(spec.get("allowed_methods"),list) and bool(spec.get("allowed_methods"))
        all_contract=all(analysis_contract.values())
        return {
            "falsifiable_question":bool(protocol.question),
            "primary_outcome_defined":bool(protocol.primary_outcome.definition),
            "transfer_defined":len(protocol.transfer_outcomes)>=1,
            "retention_defined":len(protocol.retention_timepoints)>=1,
            "control_defined":bool(protocol.control),
            "population_defined":bool(protocol.population),
            "inclusion_defined":bool(protocol.inclusion_criteria),
            "exclusion_defined":bool(protocol.exclusion_criteria),
            "sample_size_defined":protocol.sample_size_target>0,
            "allocation_defined":bool(protocol.allocation),
            "analysis_plan_defined":bool(protocol.analysis_plan),
            "analysis_contract_defined":all_contract,
            "analysis_contract_fields":analysis_contract,
            "measurement_schema_defined":all(bool(o.name and o.definition and o.unit) for o in (protocol.primary_outcome,)+protocol.transfer_outcomes),
            "status":"READY_FOR_REVIEW" if all([bool(protocol.question),bool(protocol.primary_outcome.definition),len(protocol.transfer_outcomes)>=1,len(protocol.retention_timepoints)>=1,bool(protocol.control),bool(protocol.population),bool(protocol.inclusion_criteria),bool(protocol.exclusion_criteria),protocol.sample_size_target>0,bool(protocol.allocation),bool(protocol.analysis_plan),all(bool(o.name and o.definition and o.unit) for o in (protocol.primary_outcome,)+protocol.transfer_outcomes),all_contract]) else "BLOCKED"
        }
