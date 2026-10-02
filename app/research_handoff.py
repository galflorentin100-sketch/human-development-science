"""Closed-loop handoff coordinator for governed research work.

Each handoff advances only one explicit state transition. Scientific truth,
evidence verification, skeptic review, and human-study approvals remain
separate gates.
"""
import json
from app.agent_output_gate import AgentOutputGate
from app.research_agent import ResearchAgentService
from app.research_review_agent import ResearchReviewAgentAdapter

class ResearchHandoffCoordinator:
    def __init__(self,db):
        self.db=db

    def complete_research_output(self,review_id,actor):
        review=self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))
        if not review or review["status"]!="ACCEPTED":
            raise ValueError("accepted research output review required")
        link=self.db.one("SELECT * FROM research_agent_tasks WHERE task_id=?",(review["task_id"],))
        if not link:
            raise ValueError("research agent task mapping not found")
        result=ResearchAgentService(self.db).finalize_review(review_id,actor)
        return {
            "status":"SYNTHESIS_REVIEW_REQUIRED",
            "review_id":review_id,
            "workspace_id":link["workspace_id"],
            "synthesis":result["synthesis"],
            "review_tasks":result["review_tasks"],
            "next_gate":"independent synthesis review"
        }

    def complete_review_output(self,review_id,actor):
        review=self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))
        if not review or review["status"]!="ACCEPTED":
            raise ValueError("accepted review output required")
        result=ResearchReviewAgentAdapter(self.db).finalize(review_id,actor)
        return {
            "status":"REVIEW_OUTPUT_RECORDED",
            "review_id":review_id,
            "result":result,
            "next_gate":"synthesis readiness check"
        }

    def handoff(self,review_id,actor):
        review=self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))
        if not review:
            raise ValueError("output review not found")
        link=self.db.one("SELECT * FROM research_agent_tasks WHERE task_id=?",(review["task_id"],))
        if link:
            return self.complete_research_output(review_id,actor)
        review_link=self.db.one("SELECT * FROM research_review_tasks WHERE task_id=?",(review["task_id"],))
        if review_link:
            return self.complete_review_output(review_id,actor)
        raise ValueError("review task is not part of a governed research pipeline")
