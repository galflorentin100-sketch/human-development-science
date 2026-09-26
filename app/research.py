from __future__ import annotations
import json
import hashlib
import random
from uuid import uuid4
from app.models import now
class ResearchRepository:
    def __init__(self,db): self.db=db
    def hypothesis(self,project_id,statement,status="OPEN"):
        i=str(uuid4()); self.db.execute("INSERT INTO hypotheses(id,project_id,statement,status,created_at) VALUES (?,?,?,?,?)",(i,project_id,statement,status,now())); return self.db.one("SELECT * FROM hypotheses WHERE id=?",(i,))
    def experiment(self,project_id,hypothesis,design,status="PLANNED"):
        i=str(uuid4()); self.db.execute("INSERT INTO experiments(id,project_id,hypothesis,status,design,created_at) VALUES (?,?,?,?,?,?)",(i,project_id,hypothesis,status,design,now())); return self.db.one("SELECT * FROM experiments WHERE id=?",(i,))
    def result(self,experiment_id,outcome,interpretation):
        experiment=self.db.one("SELECT * FROM experiments WHERE id=?",(experiment_id,))
        if not experiment: raise ValueError("experiment does not exist")
        if experiment["status"]=="COMPLETED": raise ValueError("experiment already has a result")
        with self.db.transaction() as con:
            if con.execute("SELECT 1 FROM experiment_results WHERE experiment_id=? LIMIT 1",(experiment_id,)).fetchone():
                raise ValueError("experiment already has a result")
            i=str(uuid4())
            con.execute("INSERT INTO experiment_results(id,experiment_id,outcome,interpretation,created_at) VALUES (?,?,?,?,?)",(i,experiment_id,outcome,interpretation,now()))
            updated=con.execute("UPDATE experiments SET result=?,status='COMPLETED' WHERE id=? AND status!='COMPLETED'",(interpretation,experiment_id))
            if getattr(updated,"rowcount",1) != 1: raise ValueError("experiment completion lost due to concurrent state change")
        return self.db.one("SELECT * FROM experiment_results WHERE id=?",(i,))
    def study(self,source_id,title,design,population,findings):
        i=str(uuid4()); self.db.execute("INSERT INTO studies(id,source_id,title,design,population,findings,created_at) VALUES (?,?,?,?,?,?,?)",(i,source_id,title,design,population,findings,now())); return self.db.one("SELECT * FROM studies WHERE id=?",(i,))
    def freeze_analysis_plan(self,study_id,analysis_spec,version=1):
        if not analysis_spec or not str(analysis_spec).strip(): raise ValueError("analysis_spec is required")
        try: parsed=json.loads(analysis_spec)
        except (TypeError,ValueError) as exc: raise ValueError("analysis_spec must be valid JSON") from exc
        if not isinstance(parsed,dict): raise ValueError("analysis_spec must be a JSON object")
        required=("outcome_name","estimand","population","estimator","ci_method","missing_data_policy","multiplicity_policy","subgroup_policy","stopping_rule","allowed_methods")
        missing=[k for k in required if not parsed.get(k)]
        if missing: raise ValueError("analysis_spec missing required fields: "+", ".join(missing))
        if not isinstance(parsed["allowed_methods"],list) or not parsed["allowed_methods"]: raise ValueError("analysis_spec.allowed_methods must be a non-empty list")
        if not self.db.one("SELECT id FROM studies WHERE id=?",(study_id,)): raise ValueError("study does not exist")
        raw=json.dumps(parsed,sort_keys=True,separators=(",",":"))
        payload=json.dumps({"spec":raw,"sha256":hashlib.sha256(raw.encode()).hexdigest()},sort_keys=True)
        i=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            if con.execute("SELECT id FROM study_analysis_plans WHERE study_id=? AND version=?",(study_id,int(version))).fetchone():
                raise ValueError("analysis plan version already exists")
            latest=con.execute("SELECT MAX(version) AS v FROM study_analysis_plans WHERE study_id=?",(study_id,)).fetchone()
            if latest and latest["v"] is not None:
                if con.execute("SELECT 1 FROM study_analysis_plans WHERE study_id=? AND frozen=1 LIMIT 1",(study_id,)).fetchone() and int(version) <= int(latest["v"]):
                    raise ValueError("analysis plan version must increase after a frozen plan")
            con.execute("INSERT INTO study_analysis_plans(id,study_id,version,analysis_spec,frozen,frozen_at,created_at) VALUES (?,?,?,?,?,?,?)",
                (i,study_id,int(version),payload,1,ts,ts))
        return self.db.one("SELECT * FROM study_analysis_plans WHERE id=?",(i,))
    def knowledge(self,project_id,kind,content,provenance):
        i=str(uuid4()); self.db.execute("INSERT INTO knowledge_items(id,project_id,kind,content,provenance,created_at) VALUES (?,?,?,?,?,?)",(i,project_id,kind,content,provenance,now())); return self.db.one("SELECT * FROM knowledge_items WHERE id=?",(i,))

class ResearchFindingService:
    VALID_SOURCES={"STUDY_RESULT","LITERATURE","MEASUREMENT","ANALYSIS","OBSERVATION","AGENT_OUTPUT"}
    VALID_CLASSIFICATIONS={"FACT","INFERENCE","HYPOTHESIS","OPINION"}
    VALID_STATUSES={"CANDIDATE","UNDER_REVIEW","ACCEPTED","REJECTED"}

    def __init__(self,db): self.db=db

    def create(self,project_id,statement,classification="HYPOTHESIS",source_type="OBSERVATION",
               source_id=None,evidence_refs=(),interpretation=None,created_by="system"):
        if classification not in self.VALID_CLASSIFICATIONS: raise ValueError("invalid finding classification")
        if source_type not in self.VALID_SOURCES: raise ValueError("invalid finding source type")
        if not statement or not statement.strip(): raise ValueError("finding statement is required")
        if classification=="FACT": raise ValueError("new findings cannot enter as FACT; submit as a candidate for review")
        i=str(uuid4())
        refs_list=list(evidence_refs or ())
        for ref in refs_list:
            ev=self.db.one("SELECT e.id,c.project_id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=?",(str(ref),))
            if not ev: raise ValueError("finding evidence reference not found")
            if str(ev["project_id"])!=str(project_id): raise ValueError("finding evidence reference belongs to another project")
        if source_type=="LITERATURE" and source_id:
            syn=self.db.one("SELECT rw.project_id FROM research_syntheses rs JOIN research_workspaces rw ON rw.id=rs.workspace_id WHERE rs.id=?",(str(source_id),))
            if syn and str(syn["project_id"])!=str(project_id): raise ValueError("finding source belongs to another project")
        refs=json.dumps(refs_list,sort_keys=True)
        self.db.execute("INSERT INTO research_findings(id,project_id,source_type,source_id,statement,classification,status,evidence_refs,interpretation,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (i,project_id,source_type,source_id,statement,classification,"CANDIDATE",refs,interpretation,created_by,now()))
        result=self.db.one("SELECT * FROM research_findings WHERE id=?",(i,))
        from app.knowledge_graph import KnowledgeDependencyGraph
        KnowledgeDependencyGraph(self.db).sync_project(project_id, created_by)
        return result

    def review(self,finding_id,reviewer,decision,rationale):
        finding=self.db.one("SELECT * FROM research_findings WHERE id=?",(finding_id,))
        if not finding: raise ValueError("finding not found")
        if decision not in {"ACCEPTED","REJECTED"}: raise ValueError("decision must be ACCEPTED or REJECTED")
        if not rationale or not rationale.strip(): raise ValueError("review rationale is required")
        if finding["created_by"]==reviewer and reviewer!="system": raise ValueError("reviewer must be independent")
        refs=json.loads(finding["evidence_refs"] or "[]")
        if not isinstance(refs,list): raise ValueError("finding evidence_refs must be a list")
        if finding["interpretation"]:
            from app.scientific_ai import ScientificAIGuard
            ScientificAIGuard().validate_interpretation(
                finding["interpretation"],
                evidence_refs=tuple(str(x) for x in refs),
                causal_design=False,
                retention_observed=False,
                transfer_observed=False,
            )
        if decision=="ACCEPTED":
            if not refs:
                raise ValueError("ACCEPTED finding requires at least one evidence reference")
            from app.evidence_pipeline import EvidencePipeline
            pipeline=EvidencePipeline(self.db)
            evidence_snapshot=[]
            for ref in refs:
                evidence=self.db.one("SELECT id,claim_id,source_id,stance,excerpt,excerpt_hash FROM evidence WHERE id=?",(str(ref),))
                if not evidence: raise ValueError("finding references unknown evidence")
                resolution=pipeline.resolve(str(ref))
                if resolution["state"]!="VERIFIED":
                    raise ValueError("ACCEPTED finding requires all referenced evidence to be VERIFIED")
                evidence_snapshot.append({"evidence_id":str(ref),"claim_id":evidence["claim_id"],"source_id":evidence["source_id"],"stance":evidence["stance"],"excerpt_hash":evidence["excerpt_hash"],"state_at_review":resolution["state"]})
        status=decision
        ts=now()
        with self.db.transaction() as con:
            updated=con.execute("UPDATE research_findings SET status=?,reviewed_by=?,reviewed_at=? WHERE id=? AND status IN ('CANDIDATE','UNDER_REVIEW')",(status,reviewer,ts,finding_id))
            if updated.rowcount != 1: raise ValueError("finding review was already resolved")
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid4()),"research_finding.reviewed","research_finding",finding_id,reviewer,json.dumps({"decision":decision,"rationale":rationale,"evidence_refs":refs,"evidence_snapshot":evidence_snapshot if decision=="ACCEPTED" else []},sort_keys=True),ts))
        return self.db.one("SELECT * FROM research_findings WHERE id=?",(finding_id,))

    def list(self,project_id,status=None):
        if status and status not in self.VALID_STATUSES: raise ValueError("invalid finding status")
        if status: return self.db.all("SELECT * FROM research_findings WHERE project_id=? AND status=? ORDER BY created_at DESC",(project_id,status))
        return self.db.all("SELECT * FROM research_findings WHERE project_id=? ORDER BY created_at DESC",(project_id,))

class StudyExecution:
    VALID_PHASES={"BASELINE","INTERVENTION","POST","FOLLOW_UP"}
    VALID_ARMS={"INTERVENTION","CONTROL"}
    def __init__(self,db): self.db=db
    def participant(self,study_id,external_ref,consent_status="CONSENTED"):
        study=self.db.one("SELECT status FROM studies WHERE id=?",(study_id,))
        if not study: raise ValueError("study does not exist")
        if study["status"] not in {"APPROVED","RUNNING"}: raise ValueError("study execution requires founder approval")
        if consent_status not in {"CONSENTED","WITHDRAWN","PENDING"}: raise ValueError("invalid consent status")
        existing=self.db.one("SELECT * FROM study_participants WHERE study_id=? AND external_ref=?",(study_id,external_ref))
        if existing:
            if existing["consent_status"] != consent_status:
                raise ValueError("participant already exists with a different consent status")
            return existing
        i=str(uuid4())
        with self.db.transaction() as con:
            race=con.execute("SELECT * FROM study_participants WHERE study_id=? AND external_ref=?",(study_id,external_ref)).fetchone()
            if race:
                if race["consent_status"] != consent_status: raise ValueError("participant already exists with a different consent status")
                return dict(race)
            con.execute("INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(i,study_id,external_ref,consent_status,now()))
        return self.db.one("SELECT * FROM study_participants WHERE id=?",(i,))
    def randomize(self,study_id,participant_id,arms=("INTERVENTION","CONTROL"),seed=None):
        if not arms or any(a not in self.VALID_ARMS for a in arms): raise ValueError("invalid study arms")
        participant=self.db.one("SELECT * FROM study_participants WHERE id=? AND study_id=?",(participant_id,study_id))
        if not participant: raise ValueError("participant does not belong to study")
        rng=random.Random(seed) if seed is not None else random.SystemRandom()
        arm=rng.choice(tuple(arms))
        i=str(uuid4())
        with self.db.transaction() as con:
            if con.execute("SELECT 1 FROM study_assignments WHERE study_id=? AND participant_id=?",(study_id,participant_id)).fetchone():
                raise ValueError("participant already assigned")
            con.execute("INSERT INTO study_assignments(id,study_id,participant_id,arm,assigned_at,method) VALUES (?,?,?,?,?,?)",(i,study_id,participant_id,arm,now(),"random_choice"))
        return self.db.one("SELECT * FROM study_assignments WHERE id=?",(i,))
    def session(self,study_id,participant_id,phase,session_number,status="COMPLETED"):
        if phase not in self.VALID_PHASES: raise ValueError("invalid study phase")
        if int(session_number) < 0: raise ValueError("session_number must be non-negative")
        i=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            if not con.execute("SELECT 1 FROM study_participants WHERE id=? AND study_id=?",(participant_id,study_id)).fetchone():
                raise ValueError("participant does not belong to study")
            if con.execute("SELECT 1 FROM study_sessions WHERE study_id=? AND participant_id=? AND phase=? AND session_number=?",
                           (study_id,participant_id,phase,int(session_number))).fetchone():
                raise ValueError("session already exists")
            con.execute("INSERT INTO study_sessions(id,study_id,participant_id,phase,session_number,occurred_at,status) VALUES (?,?,?,?,?,?,?)",
                        (i,study_id,participant_id,phase,int(session_number),ts,status))
        return self.db.one("SELECT * FROM study_sessions WHERE id=?",(i,))
    def outcome(self,study_id,participant_id,outcome_name,value=None,unit=None,session_id=None,missing_reason=None,observation_type="TRAINING",measure_id=None,timepoint=None):
        if value is None and not missing_reason: raise ValueError("missing outcome requires missing_reason")
        if observation_type not in {"TRAINING","NEAR_TRANSFER","FAR_TRANSFER","REAL_WORLD","RETENTION"}: raise ValueError("invalid observation type")
        if measure_id is not None:
            if timepoint is None: raise ValueError("timepoint is required when measure_id is supplied")
            from app.measurement import MeasurementRegistry
            binding=MeasurementRegistry(self.db).validate_observation(study_id,measure_id,observation_type,timepoint)
            if outcome_name != binding["name"]: raise ValueError("outcome name does not match preregistered measure")
        participant=self.db.one("SELECT * FROM study_participants WHERE id=? AND study_id=?",(participant_id,study_id))
        if not participant: raise ValueError("participant does not belong to study")
        study=self.db.one("SELECT status FROM studies WHERE id=?",(study_id,))
        if not study or study["status"] not in {"APPROVED","RUNNING"}: raise ValueError("study is not executable")
        if participant["consent_status"]!="CONSENTED": raise ValueError("participant consent is not active")
        if session_id and not self.db.one("SELECT 1 FROM study_sessions WHERE id=? AND study_id=? AND participant_id=?",(session_id,study_id,participant_id)): raise ValueError("session does not belong to participant")
        i=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            if session_id:
                duplicate=con.execute("SELECT 1 FROM study_outcomes WHERE study_id=? AND participant_id=? AND outcome_name=? AND observation_type=? AND session_id=?",(study_id,participant_id,outcome_name,observation_type,session_id)).fetchone()
            else:
                duplicate=con.execute("SELECT 1 FROM study_outcomes WHERE study_id=? AND participant_id=? AND outcome_name=? AND observation_type=? AND session_id IS NULL",(study_id,participant_id,outcome_name,observation_type)).fetchone()
            if duplicate:
                raise ValueError("duplicate observation")
            con.execute("INSERT INTO study_outcomes(id,study_id,participant_id,session_id,outcome_name,value,unit,missing_reason,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(i,study_id,participant_id,session_id,outcome_name,value,unit,missing_reason,observation_type,ts))
        return self.db.one("SELECT * FROM study_outcomes WHERE id=?",(i,))
    def _validate_execution_readiness(self, study_id):
        study=self.db.one("SELECT * FROM studies WHERE id=?",(study_id,))
        if not study: raise ValueError("study does not exist")
        if not study["protocol_snapshot"] or not study["protocol_hash"]:
            raise ValueError("study protocol snapshot is required before execution")
        plans=self.db.all("SELECT * FROM study_analysis_plans WHERE study_id=? AND frozen=1 ORDER BY version DESC",(study_id,))
        if not plans:
            raise ValueError("frozen analysis plan is required before execution")
        plan=plans[0]
        try:
            payload=json.loads(plan["analysis_spec"])
            spec=json.loads(payload["spec"]) if isinstance(payload.get("spec"),str) else payload.get("spec",payload)
        except (TypeError,ValueError,KeyError) as exc:
            raise ValueError("frozen analysis plan is invalid") from exc
        required=("outcome_name","estimand","population","estimator","ci_method",
                  "missing_data_policy","multiplicity_policy","subgroup_policy",
                  "stopping_rule","allowed_methods")
        missing=[k for k in required if not spec.get(k)]
        if missing or not isinstance(spec.get("allowed_methods"),list) or not spec["allowed_methods"]:
            raise ValueError("study is not execution-ready: incomplete analysis contract")
        return study,plan

    def start(self,study_id):
        study=self.db.one("SELECT * FROM studies WHERE id=?",(study_id,))
        if not study: raise ValueError("study does not exist")
        self._validate_execution_readiness(study_id)
        if study["status"]!="APPROVED": raise ValueError("founder approval required")
        with self.db.transaction() as con:
            updated=con.execute("UPDATE studies SET status='RUNNING' WHERE id=? AND status='APPROVED'",(study_id,))
            if getattr(updated,"rowcount",1) != 1:
                raise ValueError("study start lost due to concurrent state change")
        return self.db.one("SELECT * FROM studies WHERE id=?",(study_id,))
    def complete(self,study_id):
        study=self.db.one("SELECT * FROM studies WHERE id=?",(study_id,))
        if not study or study["status"]!="RUNNING": raise ValueError("study must be running")
        required={"TRAINING","NEAR_TRANSFER","FAR_TRANSFER","REAL_WORLD","RETENTION"}
        present={r["observation_type"] for r in self.db.all("SELECT DISTINCT observation_type FROM study_outcomes WHERE study_id=?",(study_id,))}
        missing=required-present
        if missing: raise ValueError("study cannot complete; missing observation types: "+",".join(sorted(missing)))
        if not self.db.one("SELECT 1 FROM study_analysis_plans WHERE study_id=? AND frozen=1",(study_id,)): raise ValueError("study cannot complete without a frozen analysis plan")
        with self.db.transaction() as con:
            updated=con.execute("UPDATE studies SET status='COMPLETED' WHERE id=? AND status='RUNNING'",(study_id,))
            if getattr(updated,"rowcount",1) != 1:
                raise ValueError("study completion lost due to concurrent state change")
        return self.db.one("SELECT * FROM studies WHERE id=?",(study_id,))
    def adherence(self,study_id,participant_id,planned,completed,session_id=None,note=""):
        if planned < 0 or completed < 0 or completed > planned: raise ValueError("invalid adherence")
        i=str(uuid4())
        self.db.execute("INSERT INTO study_adherence(id,study_id,participant_id,session_id,planned,completed,adherence_note,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(i,study_id,participant_id,session_id,int(planned),int(completed),note,now()))
        return self.db.one("SELECT * FROM study_adherence WHERE id=?",(i,))
    def freeze_analysis_plan(self,study_id,analysis_spec,version=1):
        if not analysis_spec or not str(analysis_spec).strip(): raise ValueError("analysis_spec is required")
        try:
            parsed=json.loads(analysis_spec)
        except (TypeError, ValueError) as exc:
            raise ValueError("analysis_spec must be valid JSON") from exc
        if not isinstance(parsed,dict): raise ValueError("analysis_spec must be a JSON object")
        required=("outcome_name","estimand","population","estimator","ci_method",
                  "missing_data_policy","multiplicity_policy","subgroup_policy",
                  "stopping_rule","allowed_methods")
        missing=[k for k in required if not parsed.get(k)]
        if missing: raise ValueError("analysis_spec missing required fields: "+", ".join(missing))
        if not isinstance(parsed["allowed_methods"],list) or not parsed["allowed_methods"]:
            raise ValueError("analysis_spec.allowed_methods must be a non-empty list")
        digest=hashlib.sha256(analysis_spec.encode("utf-8")).hexdigest()
        payload=json.dumps({"spec":analysis_spec,"sha256":digest},sort_keys=True)
        i=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            existing=con.execute("SELECT * FROM study_analysis_plans WHERE study_id=? AND version=?",(study_id,int(version))).fetchone()
            if existing: raise ValueError("analysis plan version already exists")
            frozen=con.execute("SELECT MAX(version) AS v FROM study_analysis_plans WHERE study_id=? AND frozen=1",(study_id,)).fetchone()
            if frozen and frozen["v"] is not None and int(version) <= int(frozen["v"]):
                raise ValueError("analysis plan version must increase after a frozen plan")
            con.execute("INSERT INTO study_analysis_plans(id,study_id,version,analysis_spec,frozen,frozen_at,created_at) VALUES (?,?,?,?,?,?,?)",
                        (i,study_id,int(version),payload,1,ts,ts))
        return self.db.one("SELECT * FROM study_analysis_plans WHERE id=?",(i,))
    def analyze_mean_change(self,study_id,analysis_plan_id,outcome_name):
        plan=self.db.one("SELECT * FROM study_analysis_plans WHERE id=?",(analysis_plan_id,))
        if not plan or not plan["frozen"]: raise ValueError("analysis plan must be frozen")
        rows=self.db.all("SELECT participant_id,value,recorded_at FROM study_outcomes WHERE study_id=? AND outcome_name=? AND value IS NOT NULL ORDER BY participant_id,recorded_at",(study_id,outcome_name))
        grouped={}
        for row in rows: grouped.setdefault(row["participant_id"],[]).append(row["value"])
        changes=[vals[-1]-vals[0] for vals in grouped.values() if len(vals)>=2]
        n_total=self.db.one("SELECT COUNT(*) AS n FROM study_participants WHERE study_id=?",(study_id,))["n"]
        estimate=sum(changes)/len(changes) if changes else None
        result={"n_total":n_total,"n_observed":len(changes),"estimate":estimate,"uncertainty":"Not estimated: no inferential model implemented.","missing_data_note":f"{n_total-len(changes)} participants lacked >=2 observed values.","interpretation":"Descriptive pre/post change only; no causal inference."}
        i=str(uuid4())
        self.db.execute("INSERT INTO study_analysis_results(id,study_id,analysis_plan_id,outcome_name,n_total,n_observed,estimate,uncertainty,missing_data_note,interpretation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(i,study_id,analysis_plan_id,outcome_name,n_total,len(changes),estimate,result["uncertainty"],result["missing_data_note"],result["interpretation"],now()))
        return self.db.one("SELECT * FROM study_analysis_results WHERE id=?",(i,))
