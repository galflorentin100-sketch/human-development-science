"""Safety-gated challenge execution and evidence-bounded adaptive training."""
from uuid import uuid4
from app.models import now

class ChallengeExecutionService:
    def __init__(self,db): self.db=db
    def start(self,project_id,challenge_id,participant_id,actor="system"):
        from app.human_development import HumanDevelopmentService
        challenge=self.db.one("""SELECT c.id,p.project_id FROM hds_challenges c
            JOIN hds_programs p ON p.id=c.program_id WHERE c.id=?""",(challenge_id,))
        if not challenge or challenge["project_id"]!=project_id:
            raise ValueError("challenge does not belong to project")
        participant=self.db.one("""SELECT cp.id,c.project_id
            FROM hds_competition_participants cp
            JOIN hds_competitions c ON c.id=cp.competition_id
            WHERE cp.id=?""",(participant_id,))
        if not participant:
            raise ValueError("participant not found")
        if participant["project_id"] != project_id:
            raise ValueError("participant does not belong to project")
        # The only supported entry point for physical challenge execution is the safety gate.
        HumanDevelopmentService(self.db).assert_challenge_safe_to_execute(challenge_id,participant_id)
        active=self.db.one("SELECT * FROM hds_challenge_executions WHERE challenge_id=? AND participant_id=? AND status='RUNNING'",(challenge_id,participant_id))
        if active: return active
        i=str(uuid4()); ts=now()
        self.db.execute("INSERT INTO hds_challenge_executions(id,project_id,challenge_id,participant_id,status,started_at,created_at) VALUES (?,?,?,?,?,?,?)",(i,project_id,challenge_id,participant_id,"RUNNING",ts,ts))
        self.db.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",(str(uuid4()),"hds.challenge.started","hds_challenge_execution",i,actor,"{}",ts))
        return self.db.one("SELECT * FROM hds_challenge_executions WHERE id=?",(i,))
    def stop(self,execution_id,reason,actor="system"):
        if not str(reason or "").strip(): raise ValueError("stop reason is required")
        row=self.db.one("SELECT * FROM hds_challenge_executions WHERE id=?",(execution_id,))
        if not row: raise ValueError("challenge execution not found")
        if row["status"]!="RUNNING": raise ValueError("challenge execution is not running")
        updated=self.db.execute("UPDATE hds_challenge_executions SET status='STOPPED',stopped_at=?,stop_reason=? WHERE id=? AND status='RUNNING'",(now(),reason.strip(),execution_id))
        if getattr(updated,"rowcount",1)!=1: raise ValueError("challenge execution changed concurrently")
        self.db.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",(str(uuid4()),"hds.challenge.stopped","hds_challenge_execution",execution_id,actor,"{}",now()))
        return self.db.one("SELECT * FROM hds_challenge_executions WHERE id=?",(execution_id,))
    def emergency_stop(self,project_id,reason,actor="system",challenge_id=None):
        if not str(reason or "").strip(): raise ValueError("emergency stop reason is required")
        query="SELECT id FROM hds_challenge_executions WHERE project_id=? AND status='RUNNING'"
        params=[project_id]
        if challenge_id:
            query += " AND challenge_id=?"
            params.append(challenge_id)
        rows=self.db.all(query,tuple(params))
        stopped=[]
        for row in rows:
            updated=self.db.execute(
                "UPDATE hds_challenge_executions SET status='STOPPED',stopped_at=?,stop_reason=? WHERE id=? AND status='RUNNING'",
                (now(),reason.strip(),row["id"]))
            if getattr(updated,"rowcount",1)==1:
                stopped.append(row["id"])
                self.db.execute(
                    "INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                    (str(uuid4()),"hds.challenge.emergency_stopped","hds_challenge_execution",row["id"],actor,
                     '{"reason":"'+reason.replace('"','\\"')+'"}',now()))
        return {"project_id":project_id,"challenge_id":challenge_id,"stopped_execution_ids":stopped,"count":len(stopped)}

    def complete(self,execution_id,actor="system"):
        row=self.db.one("SELECT * FROM hds_challenge_executions WHERE id=?",(execution_id,))
        if not row: raise ValueError("challenge execution not found")
        if row["status"]!="RUNNING": raise ValueError("challenge execution is not running")
        updated=self.db.execute("UPDATE hds_challenge_executions SET status='COMPLETED',stopped_at=? WHERE id=? AND status='RUNNING'",(now(),execution_id))
        if getattr(updated,"rowcount",1)!=1: raise ValueError("challenge execution changed concurrently")
        self.db.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",(str(uuid4()),"hds.challenge.completed","hds_challenge_execution",execution_id,actor,"{}",now()))
        return self.db.one("SELECT * FROM hds_challenge_executions WHERE id=?",(execution_id,))

class AdaptiveTrainingService:
    def __init__(self,db): self.db=db
    def recommend(self,protocol_id,participant_ref):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol: raise ValueError("training protocol not found")
        rows=self.db.all("SELECT * FROM training_sessions WHERE protocol_id=? AND participant_ref=? ORDER BY session_number DESC LIMIT 5",(protocol_id,str(participant_ref)))
        if not rows: return {"decision":"HOLD","reason":"insufficient training data","evidence_basis":"no sessions"}
        adherence=sum(int(r["adherence"]) for r in rows)/len(rows)
        fatigue=sum(1 for r in rows if str(r["fatigue_note"] or "").strip())
        successes=[float(r["task_success"]) for r in rows if r["task_success"] is not None]
        if fatigue>=2 or adherence<0.5: decision="DECREASE"
        elif successes and successes[0]>=0.8 and adherence>=0.8: decision="INCREASE"
        else: decision="HOLD"
        return {"decision":decision,"adherence":adherence,"recent_sessions":len(rows),"fatigue_flags":fatigue,"task_success_mean":sum(successes)/len(successes) if successes else None,"evidence_basis":"descriptive participant training data; not a causal efficacy claim"}
    def apply(self,project_id,protocol_id,participant_ref,new_difficulty,rationale,safety_checks=None):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol:
            raise ValueError("training protocol not found")
        if str(protocol["project_id"])!=str(project_id):
            raise ValueError("training protocol belongs to another project")
        from app.participant_governance import ParticipantGovernance
        ParticipantGovernance(self.db).assert_active(str(participant_ref))
        if not isinstance(safety_checks,dict) or not safety_checks:
            raise ValueError("current safety checks are required before adaptive training changes")
        from app.safety import SafetyGate
        safety=SafetyGate(self.db).assess(protocol_id,str(participant_ref),safety_checks)
        if safety["status"]!="CLEAR":
            raise ValueError(f"adaptive training change blocked by safety gate: {safety['status']}")
        recommendation=self.recommend(protocol_id,participant_ref)
        if not str(rationale or "").strip(): raise ValueError("rationale is required")
        if recommendation["decision"]=="HOLD": raise ValueError("adaptive change is not justified by available data")
        previous=self.db.one("SELECT new_difficulty FROM hds_training_adjustments WHERE protocol_id=? AND participant_ref=? ORDER BY created_at DESC LIMIT 1",(protocol_id,str(participant_ref)))
        i=str(uuid4()); self.db.execute("INSERT INTO hds_training_adjustments(id,project_id,protocol_id,participant_ref,previous_difficulty,new_difficulty,rationale,evidence_basis,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(i,project_id,protocol_id,str(participant_ref),previous["new_difficulty"] if previous else None,float(new_difficulty),rationale.strip(),recommendation["evidence_basis"],now()))
        return self.db.one("SELECT * FROM hds_training_adjustments WHERE id=?",(i,))
