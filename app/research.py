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
        i=str(uuid4()); self.db.execute("INSERT INTO experiment_results(id,experiment_id,outcome,interpretation,created_at) VALUES (?,?,?,?,?)",(i,experiment_id,outcome,interpretation,now())); self.db.execute("UPDATE experiments SET result=?,status='COMPLETED' WHERE id=?",(interpretation,experiment_id)); return self.db.one("SELECT * FROM experiment_results WHERE id=?",(i,))
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
        i=str(uuid4())
        self.db.execute("INSERT OR IGNORE INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",(i,study_id,external_ref,consent_status,now()))
        return self.db.one("SELECT * FROM study_participants WHERE study_id=? AND external_ref=?",(study_id,external_ref))
    def randomize(self,study_id,participant_id,arms=("INTERVENTION","CONTROL"),seed=None):
        if not arms or any(a not in self.VALID_ARMS for a in arms): raise ValueError("invalid study arms")
        if self.db.one("SELECT 1 FROM study_assignments WHERE study_id=? AND participant_id=?",(study_id,participant_id)): raise ValueError("participant already assigned")
        rng=random.Random(seed) if seed is not None else random.SystemRandom()
        arm=rng.choice(tuple(arms))
        i=str(uuid4())
        self.db.execute("INSERT INTO study_assignments(id,study_id,participant_id,arm,assigned_at,method) VALUES (?,?,?,?,?,?)",(i,study_id,participant_id,arm,now(),"random_choice"))
        return self.db.one("SELECT * FROM study_assignments WHERE id=?",(i,))
    def session(self,study_id,participant_id,phase,session_number,status="COMPLETED"):
        if phase not in self.VALID_PHASES: raise ValueError("invalid study phase")
        i=str(uuid4())
        self.db.execute("INSERT INTO study_sessions(id,study_id,participant_id,phase,session_number,occurred_at,status) VALUES (?,?,?,?,?,?,?)",(i,study_id,participant_id,phase,int(session_number),now(),status))
        return self.db.one("SELECT * FROM study_sessions WHERE id=?",(i,))
    def outcome(self,study_id,participant_id,outcome_name,value=None,unit=None,session_id=None,missing_reason=None):
        if value is None and not missing_reason: raise ValueError("missing outcome requires missing_reason")
        i=str(uuid4())
        self.db.execute("INSERT INTO study_outcomes(id,study_id,participant_id,session_id,outcome_name,value,unit,missing_reason,recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",(i,study_id,participant_id,session_id,outcome_name,value,unit,missing_reason,now()))
        return self.db.one("SELECT * FROM study_outcomes WHERE id=?",(i,))
    def adherence(self,study_id,participant_id,planned,completed,session_id=None,note=""):
        if planned < 0 or completed < 0 or completed > planned: raise ValueError("invalid adherence")
        i=str(uuid4())
        self.db.execute("INSERT INTO study_adherence(id,study_id,participant_id,session_id,planned,completed,adherence_note,recorded_at) VALUES (?,?,?,?,?,?,?,?)",(i,study_id,participant_id,session_id,int(planned),int(completed),note,now()))
        return self.db.one("SELECT * FROM study_adherence WHERE id=?",(i,))
    def freeze_analysis_plan(self,study_id,analysis_spec,version=1):
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
