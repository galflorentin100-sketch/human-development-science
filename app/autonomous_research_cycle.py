"""Governed autonomous research cycle.

Automation proposes work and creates candidates; scientific state changes remain
behind explicit review/approval gates.
"""
from app.research_queue import ResearchQueue
from app.contradiction_engine import ContradictionEngine
from app.scientific_integrity import ScientificIntegrityChecker

class AutonomousResearchCycle:
    def __init__(self, db):
        self.db=db

    def run(self, project_id):
        integrity=ScientificIntegrityChecker(self.db).project(project_id)
        contradictions=ContradictionEngine(self.db).list(project_id)
        queue=ResearchQueue(self.db)
        proposed=[]
        for issue in integrity["issues"]:
            proposed.append(queue.propose(
                project_id,
                "Resolve scientific integrity issue: "+issue["type"],
                "Automated integrity scan detected a review-required condition.",
                "INTEGRITY_SCAN",
                priority="CRITICAL"))
        for item in contradictions:
            proposed.append(queue.propose(
                project_id,
                "Review contradictory evidence",
                item["description"],
                "CONTRADICTION",
                evidence_refs=(item["evidence_a"],item["evidence_b"]),
                priority="CRITICAL"))
        if not proposed and integrity["integrity"]=="PASS" and not contradictions:
            proposed.append(queue.propose(
                project_id,
                "Identify the next testable research question",
                "No blocking integrity or contradiction issue was detected.",
                "DISCOVERY",
                priority="NORMAL"))
        return {
            "project_id":project_id,
            "integrity":integrity,
            "open_contradictions":contradictions,
            "proposed_research":proposed,
            "requires_human_review":bool(proposed),
        }
