"""Closed-loop handoff for governed autonomous research.

This coordinator connects completed research work products to provenance sync and
the next deterministic gap scan. It never promotes scientific truth or bypasses
review, safety, or human-participant governance.
"""
from app.knowledge_graph import KnowledgeDependencyGraph
from app.research_question_generator import ResearchQuestionGenerator

class ResearchLoopCoordinator:
    def __init__(self,db):
        self.db=db

    def after_review(self,synthesis_id,actor="system"):
        syn=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))
        if not syn: raise ValueError("synthesis not found")
        ws=self.db.one("SELECT * FROM research_workspaces WHERE id=?",(syn["workspace_id"],))
        if not ws: raise ValueError("research workspace not found")
        if syn["status"]!="ACCEPTED":
            raise ValueError("closed-loop handoff requires an ACCEPTED synthesis")
        project_id=ws["project_id"]
        graph=KnowledgeDependencyGraph(self.db).sync_project(project_id,actor=actor)
        gaps=ResearchQuestionGenerator(self.db).generate(project_id)
        return {
            "status":"HANDOFF_COMPLETE",
            "project_id":project_id,
            "synthesis_id":synthesis_id,
            "graph_sync":graph,
            "gap_report":gaps,
            "policy":"handoff only; downstream findings and scientific truth remain separately gated"
        }
