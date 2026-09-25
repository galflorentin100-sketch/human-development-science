"""Founder-facing scientific/company intelligence snapshot."""
from app.scientific_integrity import ScientificIntegrityChecker
from app.contradiction_engine import ContradictionEngine
from app.research_queue import ResearchQueue
from app.experiment_engine import ExperimentEngine
from app.decision_center import DecisionCenter

class FounderIntelligence:
    def __init__(self, db): self.db=db

    def snapshot(self, project_id):
        integrity=ScientificIntegrityChecker(self.db).project(project_id)
        contradictions=ContradictionEngine(self.db).list(project_id)
        queue=ResearchQueue(self.db).list(project_id)
        experiments=ExperimentEngine(self.db).list(project_id)
        tasks=self.db.all("SELECT status, COUNT(*) n FROM tasks WHERE project_id=? GROUP BY status",(project_id,))
        decisions=DecisionCenter(self.db).list(project_id)
        return {
            "project_id":project_id,
            "scientific_health":{
                "integrity":integrity["integrity"],
                "integrity_issues":len(integrity["issues"]),
                "open_contradictions":len(contradictions),
                "decision_queue":len(decisions),
                "high_priority_decisions":sum(1 for x in decisions if x["priority"] in {"HIGH","CRITICAL"}),
            },
            "research":{
                "proposed":sum(1 for x in queue if x["status"]=="PROPOSED"),
                "approved":sum(1 for x in queue if x["status"]=="APPROVED"),
                "in_progress":sum(1 for x in queue if x["status"]=="IN_PROGRESS"),
                "completed":sum(1 for x in queue if x["status"]=="DONE"),
            },
            "experiments":{
                "draft":sum(1 for x in experiments if x["status"]=="DRAFT"),
                "ready":sum(1 for x in experiments if x["status"]=="READY"),
                "running":sum(1 for x in experiments if x["status"]=="RUNNING"),
                "completed":sum(1 for x in experiments if x["status"]=="COMPLETED"),
            },
            "work_queue":[dict(x) for x in tasks],
            "requires_founder_attention": bool(integrity["issues"] or contradictions or decisions),
        }
