from __future__ import annotations
import json
from uuid import uuid4
from app.models import now


class TrainingProtocolService:
    EVIDENCE_LEVELS={"UNTESTED","PLAUSIBLE","PRELIMINARY","SUPPORTED","WELL_SUPPORTED"}
    STATUSES={"DRAFT","PILOT","SUPPORTED","RETIRED"}

    def __init__(self,db):
        self.db=db

    def create(self,project_id,name,mechanism_hypothesis,challenge_domain,dosage,
               progression_rule,transfer_target,retention_target,safety_constraints,
               evidence_level="UNTESTED",target_construct_id=None,status="DRAFT",version=1):
        if evidence_level not in self.EVIDENCE_LEVELS:
            raise ValueError("invalid training protocol evidence level")
        if status not in self.STATUSES:
            raise ValueError("invalid training protocol status")
        required={
            "name":name,"mechanism_hypothesis":mechanism_hypothesis,
            "challenge_domain":challenge_domain,"dosage":dosage,
            "progression_rule":progression_rule,"transfer_target":transfer_target,
            "retention_target":retention_target,"safety_constraints":safety_constraints,
        }
        if any(not str(v or "").strip() for v in required.values()):
            raise ValueError("training protocol fields are required")
        if target_construct_id and not self.db.one("SELECT 1 FROM scientific_constructs WHERE id=?",(target_construct_id,)):
            raise ValueError("target construct not found")
        i=str(uuid4())
        self.db.execute(
            "INSERT INTO training_protocols(id,project_id,name,target_construct_id,mechanism_hypothesis,challenge_domain,dosage,progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,version,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (i,project_id,name,target_construct_id,mechanism_hypothesis,challenge_domain,dosage,
             progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,int(version),now())
        )
        return self.db.one("SELECT * FROM training_protocols WHERE id=?",(i,))

    def attach_evidence(self,protocol_id,evidence_kind,evidence_ref,notes=""):
        if not self.db.one("SELECT 1 FROM training_protocols WHERE id=?",(protocol_id,)):
            raise ValueError("training protocol not found")
        if not evidence_kind or not evidence_ref:
            raise ValueError("evidence kind and reference are required")
        i=str(uuid4())
        self.db.execute(
            "INSERT INTO training_protocol_evidence(id,protocol_id,evidence_kind,evidence_ref,notes,created_at) VALUES (?,?,?,?,?,?)",
            (i,protocol_id,evidence_kind,evidence_ref,notes or "",now())
        )
        return self.db.one("SELECT * FROM training_protocol_evidence WHERE id=?",(i,))

    def session(self,protocol_id,participant_ref,session_number,load_note,adherence,
                task_success=None,transfer_score=None,retention_score=None,
                decision_accuracy=None,initiation_latency=None,recovery_score=None,
                fatigue_note=""):
        if not self.db.one("SELECT 1 FROM training_protocols WHERE id=?",(protocol_id,)):
            raise ValueError("training protocol not found")
        if int(session_number)<1:
            raise ValueError("session_number must be positive")
        if int(adherence) not in {0,1}:
            raise ValueError("adherence must be 0 or 1")
        if not str(load_note or "").strip():
            raise ValueError("load_note is required")
        i=str(uuid4())
        self.db.execute(
            "INSERT INTO training_sessions(id,protocol_id,participant_ref,session_number,load_note,adherence,task_success,transfer_score,retention_score,decision_accuracy,initiation_latency,recovery_score,fatigue_note,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (i,protocol_id,str(participant_ref),int(session_number),load_note,int(adherence),
             task_success,transfer_score,retention_score,decision_accuracy,initiation_latency,
             recovery_score,fatigue_note or "",now())
        )
        return self.db.one("SELECT * FROM training_sessions WHERE id=?",(i,))

    def readiness(self,protocol_id):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol:
            raise ValueError("training protocol not found")
        evidence=self.db.all("SELECT * FROM training_protocol_evidence WHERE protocol_id=? ORDER BY created_at",(protocol_id,))
        return {
            "protocol_id":protocol_id,
            "status":protocol["status"],
            "evidence_level":protocol["evidence_level"],
            "evidence_count":len(evidence),
            "has_transfer_target":bool(protocol["transfer_target"].strip()),
            "has_retention_target":bool(protocol["retention_target"].strip()),
            "has_safety_constraints":bool(protocol["safety_constraints"].strip()),
            "ready_for_pilot":protocol["status"] in {"DRAFT","PILOT"} and bool(protocol["safety_constraints"].strip()),
        }

    def list(self,project_id,status=None):
        if status and status not in self.STATUSES:
            raise ValueError("invalid training protocol status")
        if status:
            return self.db.all("SELECT * FROM training_protocols WHERE project_id=? AND status=? ORDER BY created_at DESC",(project_id,status))
        return self.db.all("SELECT * FROM training_protocols WHERE project_id=? ORDER BY created_at DESC",(project_id,))
