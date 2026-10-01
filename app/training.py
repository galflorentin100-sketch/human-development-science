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
               evidence_level="UNTESTED",target_construct_id=None,status="DRAFT",version=1,source_claim_id=None,intervention_id=None):
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
        if target_construct_id:
            construct=self.db.one("SELECT project_id FROM scientific_constructs WHERE id=?",(target_construct_id,))
            if not construct: raise ValueError("target construct not found")
            if construct["project_id"] is not None and str(construct["project_id"])!=str(project_id):
                raise ValueError("target construct belongs to another project")
        if source_claim_id:
            claim=self.db.one("SELECT project_id FROM claims WHERE id=?",(source_claim_id,))
            if not claim: raise ValueError("source claim not found")
            if str(claim["project_id"])!=str(project_id): raise ValueError("source claim belongs to another project")
        if intervention_id:
            intervention=self.db.one("SELECT project_id FROM interventions WHERE id=?",(intervention_id,))
            if not intervention: raise ValueError("intervention not found")
            if str(intervention["project_id"])!=str(project_id): raise ValueError("intervention belongs to another project")
        i=str(uuid4())
        self.db.execute(
            "INSERT INTO training_protocols(id,project_id,name,target_construct_id,source_claim_id,intervention_id,mechanism_hypothesis,challenge_domain,dosage,progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,version,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (i,project_id,name,target_construct_id,source_claim_id,intervention_id,mechanism_hypothesis,challenge_domain,dosage,
             progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,int(version),now())
        )
        result=self.db.one("SELECT * FROM training_protocols WHERE id=?",(i,))
        from app.knowledge_graph import KnowledgeDependencyGraph
        KnowledgeDependencyGraph(self.db).sync_project(project_id)
        return result

    def link_basis(self,protocol_id,source_claim_id=None,intervention_id=None):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol: raise ValueError("training protocol not found")
        if source_claim_id is not None:
            claim=self.db.one("SELECT project_id FROM claims WHERE id=?",(source_claim_id,))
            if not claim: raise ValueError("source claim not found")
            if str(claim["project_id"])!=str(protocol["project_id"]): raise ValueError("source claim belongs to another project")
        if intervention_id is not None:
            intervention=self.db.one("SELECT project_id FROM interventions WHERE id=?",(intervention_id,))
            if not intervention: raise ValueError("intervention not found")
            if str(intervention["project_id"])!=str(protocol["project_id"]): raise ValueError("intervention belongs to another project")
        if source_claim_id is None and intervention_id is None:
            raise ValueError("scientific basis requires a source claim or intervention")
        self.db.execute("UPDATE training_protocols SET source_claim_id=?, intervention_id=? WHERE id=?",(source_claim_id,intervention_id,protocol_id))
        return self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))

    def attach_evidence(self,protocol_id,evidence_kind,evidence_ref,notes=""):
        protocol=self.db.one("SELECT project_id FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol:
            raise ValueError("training protocol not found")
        if not evidence_kind or not evidence_ref:
            raise ValueError("evidence kind and reference are required")
        evidence=self.db.one(
            "SELECT e.id,c.project_id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=?",
            (str(evidence_ref),))
        if not evidence:
            raise ValueError("training protocol evidence reference not found")
        if str(evidence["project_id"])!=str(protocol["project_id"]):
            raise ValueError("training protocol evidence belongs to another project")
        i=str(uuid4())
        self.db.execute(
            "INSERT INTO training_protocol_evidence(id,protocol_id,evidence_kind,evidence_ref,notes,created_at) VALUES (?,?,?,?,?,?)",
            (i,protocol_id,evidence_kind,evidence_ref,notes or "",now())
        )
        return self.db.one("SELECT * FROM training_protocol_evidence WHERE id=?",(i,))

    def progression(self,protocol_id,participant_ref):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol: raise ValueError("training protocol not found")
        rows=self.db.all("SELECT session_number,adherence,task_success,transfer_score,retention_score,decision_accuracy,initiation_latency,recovery_score,fatigue_note FROM training_sessions WHERE protocol_id=? AND participant_ref=? ORDER BY session_number",(protocol_id,str(participant_ref)))
        completed=sum(int(r["adherence"]) for r in rows)
        return {"protocol_id":protocol_id,"participant_ref":str(participant_ref),"sessions":rows,"completed_sessions":completed,"total_sessions":len(rows),"progression_rule":protocol["progression_rule"],"evidence_level":protocol["evidence_level"]}

    def session(self,protocol_id,participant_ref,session_number,load_note,adherence,
                task_success=None,transfer_score=None,retention_score=None,
                decision_accuracy=None,initiation_latency=None,recovery_score=None,
                fatigue_note="",safety_checks=None):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol:
            raise ValueError("training protocol not found")
        from app.participant_governance import ParticipantGovernance
        ParticipantGovernance(self.db).assert_active(str(participant_ref))
        if not isinstance(safety_checks,dict) or not safety_checks:
            raise ValueError("current safety checks are required before recording a training session")
        from app.safety import SafetyGate
        safety=SafetyGate(self.db).assess(protocol_id,str(participant_ref),safety_checks)
        if safety["status"]!="CLEAR":
            raise ValueError(f"training session blocked by safety gate: {safety['status']}")
        if protocol["status"]=="RETIRED":
            raise ValueError("retired training protocols cannot accept new sessions")
        if int(session_number)<1:
            raise ValueError("session_number must be positive")
        if int(adherence) not in {0,1}:
            raise ValueError("adherence must be 0 or 1")
        if not str(load_note or "").strip():
            raise ValueError("load_note is required")
        i=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            participant=con.execute(
                "SELECT consent_status,withdrawn_at FROM participant_governance WHERE participant_ref=?",
                (str(participant_ref),),
            ).fetchone()
            if not participant or participant["consent_status"]!="CONSENTED" or participant["withdrawn_at"]:
                raise ValueError("participant is not actively consented")
            unresolved=con.execute(
                "SELECT 1 FROM training_adverse_events WHERE participant_ref=? AND resolved=0 LIMIT 1",
                (str(participant_ref),),
            ).fetchone()
            if unresolved:
                raise ValueError("participant has an unresolved adverse event; training is blocked pending review")
            if con.execute("SELECT 1 FROM training_sessions WHERE protocol_id=? AND participant_ref=? AND session_number=?",
                           (protocol_id,str(participant_ref),int(session_number))).fetchone():
                raise ValueError("training session already exists")
            con.execute(
                "INSERT INTO training_sessions(id,protocol_id,participant_ref,session_number,load_note,adherence,task_success,transfer_score,retention_score,decision_accuracy,initiation_latency,recovery_score,fatigue_note,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(protocol_id,participant_ref,session_number) DO NOTHING",
                (i,protocol_id,str(participant_ref),int(session_number),load_note,int(adherence),
                 task_success,transfer_score,retention_score,decision_accuracy,initiation_latency,
                 recovery_score,fatigue_note or "",ts)
            )
        result=self.db.one("SELECT * FROM training_sessions WHERE id=?",(i,))
        if not result:
            result=self.db.one("SELECT * FROM training_sessions WHERE protocol_id=? AND participant_ref=? AND session_number=?",
                               (protocol_id,str(participant_ref),int(session_number)))
        return result

    def _evidence_readiness(self,protocol_id):
        from app.evidence_pipeline import EvidencePipeline
        rows=self.db.all("SELECT evidence_ref,evidence_kind FROM training_protocol_evidence WHERE protocol_id=?",(protocol_id,))
        resolved=[]
        for row in rows:
            try: resolved.append(EvidencePipeline(self.db).resolve(row["evidence_ref"]))
            except ValueError: resolved.append({"state":"MISSING","evidence_id":row["evidence_ref"]})
        return resolved

    def promote(self,protocol_id,new_status,actor,rationale):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol: raise ValueError("training protocol not found")
        if new_status not in self.STATUSES: raise ValueError("invalid training protocol status")
        if not rationale or not rationale.strip(): raise ValueError("promotion rationale is required")
        old=protocol["status"]
        allowed={"DRAFT":{"PILOT","RETIRED"},"PILOT":{"SUPPORTED","RETIRED"},"SUPPORTED":{"RETIRED"},"RETIRED":set()}
        if new_status not in allowed.get(old,set()): raise ValueError(f"invalid training protocol transition: {old} -> {new_status}")
        if new_status in {"PILOT","SUPPORTED"}:
            from app.scientific_admission import ScientificAdmissionGate
            ScientificAdmissionGate(self.db).assert_training_admissible(protocol_id,new_status)
        if new_status=="SUPPORTED":
            evidence=self._evidence_readiness(protocol_id)
            if not evidence or any(x["state"]!="VERIFIED" for x in evidence):
                raise ValueError("SUPPORTED training protocol requires all attached evidence to be VERIFIED")
            sessions=self.db.all("SELECT * FROM training_sessions WHERE protocol_id=? ORDER BY session_number",(protocol_id,))
            if not sessions: raise ValueError("SUPPORTED training protocol requires training sessions")
            if not any(s["transfer_score"] is not None for s in sessions):
                raise ValueError("SUPPORTED training protocol requires observed transfer data")
            if not any(s["retention_score"] is not None for s in sessions):
                raise ValueError("SUPPORTED training protocol requires observed retention data")
        ts=now()
        with self.db.transaction() as con:
            updated=con.execute("UPDATE training_protocols SET status=? WHERE id=? AND status=?",(new_status,protocol_id,old))
            if updated.rowcount != 1:
                raise ValueError("training protocol state changed concurrently")
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid4()),"training_protocol.status_changed","training_protocol",protocol_id,actor,json.dumps({"from":old,"to":new_status,"rationale":rationale},sort_keys=True),ts))
        return self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))

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
            "scientific_basis":{"source_claim_id":protocol["source_claim_id"],"intervention_id":protocol["intervention_id"]},
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
