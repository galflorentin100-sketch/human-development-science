"""Closed-loop handoff coordinator for governed research work.

Each handoff advances only one explicit state transition. Scientific truth,
evidence verification, skeptic review, and human-study approvals remain
separate gates.
"""
import json
from app.agent_output_gate import AgentOutputGate
from app.research_agent import ResearchAgentService
from app.research_review_agent import ResearchReviewAgentAdapter
from app.knowledge_graph import KnowledgeDependencyGraph
from app.research_question_generator import ResearchQuestionGenerator

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

    def complete_accepted_synthesis(self,project_id,synthesis_id,actor="system"):
        if not self.db.one(
            """SELECT rs.id
               FROM research_syntheses rs
               JOIN research_workspaces rw ON rw.id=rs.workspace_id
               WHERE rs.id=? AND rs.status='ACCEPTED' AND rw.project_id=?""",
            (synthesis_id,project_id)):
            raise ValueError("accepted synthesis not found in project")
        graph=KnowledgeDependencyGraph(self.db).sync_project(project_id,actor=actor)
        gaps=ResearchQuestionGenerator(self.db).generate(project_id)
        return {
            "status":"LOOP_CONTINUES",
            "project_id":project_id,
            "synthesis_id":synthesis_id,
            "graph_sync":graph,
            "gap_report":gaps,
            "next_gate":"autonomous question selection",
            "policy":"handoff discovers downstream work only; no scientific truth or sensitive execution is authorized"
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
