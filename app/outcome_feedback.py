"""Controlled feedback from measured study/training outcomes into scientific findings.

Observed outcomes are never silently promoted to facts. They enter as candidate findings
with explicit provenance and require independent review before acceptance.
"""
import json
from app.research import ResearchFindingService


class OutcomeFeedbackService:
    def __init__(self,db):
        self.db=db

    def propose_research_from_study(self, study_id, outcome_name, observation_type="TRAINING", created_by="system"):
        candidate=self.propose_from_study(study_id,outcome_name,observation_type,created_by)
        from app.research_queue import ResearchQueue
        finding=self.db.one("SELECT * FROM research_findings WHERE id=?",(candidate["finding_id"],))
        question=f"Investigate the observed outcome pattern: {outcome_name}"
        queue=ResearchQueue(self.db).propose(
            finding["project_id"], question,
            "Outcome feedback created a descriptive candidate finding; further research is required before causal or generalization claims.",
            "OUTCOME_FEEDBACK", priority="NORMAL")
        return {"finding":candidate,"research_proposal":queue,"scientific_status":"CANDIDATE_ONLY"}

    def propose_from_study(self, study_id, outcome_name, observation_type="TRAINING", created_by="system"):
        study=self.db.one("SELECT * FROM studies WHERE id=?",(study_id,))
        if not study:
            raise ValueError("study not found")
        rows=self.db.all("""SELECT participant_id,value,unit,session_id,missing_reason
                            FROM study_outcomes
                            WHERE study_id=? AND outcome_name=? AND observation_type=?
                            ORDER BY recorded_at""",(study_id,outcome_name,observation_type))
        if not rows:
            raise ValueError("no observed outcomes found")
        observed=[r for r in rows if r["value"] is not None]
        if not observed:
            raise ValueError("all outcomes are missing")
        values=[float(r["value"]) for r in observed]
        summary={"n":len(values),"mean":sum(values)/len(values),"min":min(values),"max":max(values),"unit":observed[0]["unit"]}
        statement=f"Observed {len(values)} recorded {outcome_name} observations in study {study_id}."
        interpretation=f"Descriptive observation only; mean={summary['mean']}. This does not establish causality or transfer."

        finding=ResearchFindingService(self.db).create(
            project_id=study["project_id"],
            statement=statement,
            classification="INFERENCE",
            source_type="STUDY_RESULT",
            source_id=study_id,
            evidence_refs=(),
            interpretation=interpretation,
            created_by=created_by,
        )
        return {
            "finding_id":finding["id"],
            "summary":summary,
            "provenance":{"study_id":study_id,"outcome_name":outcome_name,"observation_type":observation_type},
            "status":finding["status"],
        }

    def propose_from_training(self, protocol_id, participant_ref=None, created_by="system"):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol:
            raise ValueError("training protocol not found")
        if participant_ref:
            rows=self.db.all("SELECT * FROM training_sessions WHERE protocol_id=? AND participant_ref=? ORDER BY session_number",(protocol_id,participant_ref))
        else:
            rows=self.db.all("SELECT * FROM training_sessions WHERE protocol_id=? ORDER BY created_at",(protocol_id,))
        if not rows:
            raise ValueError("no training sessions found")
        success=[r["task_success"] for r in rows if r["task_success"] is not None]
        transfer=[r["transfer_score"] for r in rows if r["transfer_score"] is not None]
        retention=[r["retention_score"] for r in rows if r["retention_score"] is not None]
        summary={"sessions":len(rows),"task_success_mean":sum(success)/len(success) if success else None,
                 "transfer_mean":sum(transfer)/len(transfer) if transfer else None,
                 "retention_mean":sum(retention)/len(retention) if retention else None}
        statement=f"Observed training-session data for protocol {protocol_id} across {len(rows)} sessions."

        finding=ResearchFindingService(self.db).create(
            project_id=protocol["project_id"],
            statement=statement,
            classification="INFERENCE",
            source_type="TRAINING_PROTOCOL",
            source_id=protocol_id,
            evidence_refs=(),
            interpretation="Observed training measurements; no causal or generalization claim is made.",
            created_by=created_by,
        )
        return {
            "finding_id":finding["id"],
            "summary":summary,
            "provenance":{"protocol_id":protocol_id,"participant_ref":participant_ref},
            "status":finding["status"],
        }
