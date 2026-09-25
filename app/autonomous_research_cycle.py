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

    def _propose_once(self, queue, project_id, question, rationale, trigger_type, evidence_refs=(), priority="NORMAL"):
        existing=self.db.one(
            "SELECT * FROM hds_research_queue WHERE project_id=? AND question=? AND status IN ('PROPOSED','APPROVED','IN_PROGRESS')",
            (project_id, question),
        )
        if existing:
            return existing
        return queue.propose(project_id, question, rationale, trigger_type, evidence_refs=evidence_refs, priority=priority)

    def run(self, project_id):
        integrity=ScientificIntegrityChecker(self.db).project(project_id)
        contradictions=ContradictionEngine(self.db).list(project_id)
        queue=ResearchQueue(self.db)
        proposed=[]
        for issue in integrity["issues"]:
            proposed.append(self._propose_once(queue,
                project_id,
                "Resolve scientific integrity issue: "+issue["type"],
                "Automated integrity scan detected a review-required condition.",
                "INTEGRITY_SCAN",
                priority="CRITICAL"))
        for item in contradictions:
            proposed.append(self._propose_once(queue,
                project_id,
                "Review contradictory evidence",
                item["description"],
                "CONTRADICTION",
                evidence_refs=(item["evidence_a"],item["evidence_b"]),
                priority="CRITICAL"))
        if not proposed and integrity["integrity"]=="PASS" and not contradictions:
            proposed.append(self._propose_once(queue,
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
