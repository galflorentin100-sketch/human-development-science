"""Deterministic closed-loop scientific state engine.

This module composes existing HDS scientific services. It is intentionally
read-oriented: it reports what is known, missing, conflicting, and observed;
it does not promote claims or infer causality.
"""
from app.scientific_training_pipeline import ScientificTrainingPipeline
from app.training_outcomes import TrainingOutcomeAnalyzer
from app.scientific_admission import ScientificAdmissionGate

class ClosedLoopEngine:
    def __init__(self, db):
        self.db = db

    def protocol(self, protocol_id):
        graph = ScientificTrainingPipeline(self.db).trace(protocol_id)
        readiness = ScientificTrainingPipeline(self.db).readiness(protocol_id)
        outcomes = TrainingOutcomeAnalyzer(self.db).summarize(protocol_id)
        p = graph["protocol"]
        admission = ScientificAdmissionGate(self.db).training(protocol_id)
        return {
            "stage": "PROTOCOL_ANALYSIS",
            "protocol_id": protocol_id,
            "provenance": graph,
            "readiness": readiness,
            "admission": admission,
            "outcomes": outcomes,
            "interpretation": (
                "This snapshot is descriptive and provenance-oriented. "
                "It does not establish intervention efficacy or causality."
            ),
        }

    def project(self, project_id):
        protocols = self.db.all(
            "SELECT id FROM training_protocols WHERE project_id=? ORDER BY created_at",
            (project_id,),
        )
        findings = self.db.all(
            "SELECT * FROM research_findings WHERE project_id=? ORDER BY created_at DESC",
            (project_id,),
        )
        claims = self.db.all(
            "SELECT * FROM claims WHERE project_id=? ORDER BY created_at DESC",
            (project_id,),
        )
        return {
            "stage": "PROJECT_CLOSED_LOOP",
            "project_id": project_id,
            "protocols": [self.protocol(p["id"]) for p in protocols],
            "findings": findings,
            "claims": claims,
            "next_actions": self.next_actions(project_id),
        }

    def next_actions(self, project_id):
        actions = []
        missing = self.db.all(
            """SELECT tp.id, tp.name FROM training_protocols tp
               WHERE tp.project_id=? AND NOT EXISTS
               (SELECT 1 FROM training_protocol_evidence tpe
                WHERE tpe.protocol_id=tp.id)""",
            (project_id,),
        )
        for row in missing:
            actions.append({
                "type": "EVIDENCE_GAP",
                "priority": "HIGH",
                "protocol_id": row["id"],
                "reason": "training protocol has no attached evidence",
            })

        conflicts = self.db.all(
            """SELECT DISTINCT tp.id, tp.name
               FROM training_protocols tp
               JOIN training_protocol_evidence tpe ON tpe.protocol_id=tp.id
               WHERE tp.project_id=?""",
            (project_id,),
        )
        for row in conflicts:
            readiness = ScientificTrainingPipeline(self.db).readiness(row["id"])
            if "conflicting_evidence" in readiness["blockers"]:
                actions.append({
                    "type": "CONTRADICTION_REVIEW",
                    "priority": "CRITICAL",
                    "protocol_id": row["id"],
                    "reason": "conflicting evidence blocks scientific review",
                })

        uncertain = self.db.all(
            "SELECT id FROM claims WHERE project_id=? AND status='UNCERTAIN'",
            (project_id,),
        )
        if uncertain:
            actions.append({
                "type": "CLAIM_REVIEW",
                "priority": "HIGH",
                "reason": f"{len(uncertain)} uncertain claim(s) require review",
            })

        if not actions:
            actions.append({
                "type": "RESEARCH_DISCOVERY",
                "priority": "NORMAL",
                "reason": "no blocking scientific action detected; generate the next testable question",
            })
        return actions
