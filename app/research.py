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
    def knowledge(self,project_id,kind,content,provenance):
        i=str(uuid4()); self.db.execute("INSERT INTO knowledge_items(id,project_id,kind,content,provenance,created_at) VALUES (?,?,?,?,?,?)",(i,project_id,kind,content,provenance,now())); return self.db.one("SELECT * FROM knowledge_items WHERE id=?",(i,))

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
        if not self.db.one("SELECT 1 FROM study_participants WHERE id=? AND study_id=?",(participant_id,study_id)):
            raise ValueError("participant does not belong to study")
        i=str(uuid4())
        self.db.execute("INSERT INTO study_sessions(id,study_id,participant_id,phase,session_number,occurred_at,status) VALUES (?,?,?,?,?,?,?)",(i,study_id,participant_id,phase,int(session_number),now(),status))
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
        if self.db.one("SELECT 1 FROM study_outcomes WHERE study_id=? AND participant_id=? AND outcome_name=? AND observation_type=? AND (session_id=? OR (session_id IS NULL AND ? IS NULL))",(study_id,participant_id,outcome_name,observation_type,session_id,session_id)): raise ValueError("duplicate observation")
        i=str(uuid4())
        self.db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,session_id,outcome_name,value,unit,missing_reason,observation_type,recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(i,study_id,participant_id,session_id,outcome_name,value,unit,missing_reason,observation_type,now()))
        return self.db.one("SELECT * FROM study_outcomes WHERE id=?",(i,))
    def start(self,study_id):
        study=self.db.one("SELECT * FROM studies WHERE id=?",(study_id,))
        if not study: raise ValueError("study does not exist")
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
        if not isinstance(parsed,dict):
            raise ValueError("analysis_spec must be a JSON object")
        required=("outcome_name","estimand","population","estimator","ci_method",
                  "missing_data_policy","multiplicity_policy","subgroup_policy",
                  "stopping_rule","allowed_methods")
        missing=[k for k in required if not parsed.get(k)]
        if missing:
            raise ValueError("analysis_spec missing required fields: "+", ".join(missing))
        if not isinstance(parsed["allowed_methods"],list) or not parsed["allowed_methods"]:
            raise ValueError("analysis_spec.allowed_methods must be a non-empty list")
        existing=self.db.one("SELECT * FROM study_analysis_plans WHERE study_id=? AND version=?",(study_id,int(version)))
        if existing: raise ValueError("analysis plan version already exists")
        frozen=self.db.one("SELECT 1 FROM study_analysis_plans WHERE study_id=? AND frozen=1",(study_id,))
        if frozen and int(version) <= int(self.db.one("SELECT MAX(version) AS v FROM study_analysis_plans WHERE study_id=?",(study_id,))["v"]): raise ValueError("analysis plan version must increase after a frozen plan")
        digest=hashlib.sha256(analysis_spec.encode("utf-8")).hexdigest()
        payload=json.dumps({"spec":analysis_spec,"sha256":digest},sort_keys=True)
        i=str(uuid4())
        self.db.execute("INSERT INTO study_analysis_plans(id,study_id,version,analysis_spec,frozen,frozen_at,created_at) VALUES (?,?,?,?,?,?,?)",(i,study_id,int(version),payload,1,now(),now()))
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
