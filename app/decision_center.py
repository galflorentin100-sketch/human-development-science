"""Unified founder decision center.

Read-only aggregation plus explicit approval actions. It does not execute
scientific mutations itself; domain services remain responsible for gates.
"""
from app.approvals import ApprovalService
from app.research_queue import ResearchQueue
from app.contradiction_engine import ContradictionEngine
from app.claim_revision import ClaimRevisionService
from app.knowledge_impact_engine import KnowledgeImpactEngine

class DecisionCenter:
    def __init__(self,db): self.db=db

    def list(self,project_id):
        items=[]
        for r in ResearchQueue(self.db).list(project_id):
            if r["status"]=="PROPOSED":
                items.append({"type":"RESEARCH","id":r["id"],"priority":r["priority"],"title":r["question"],"reason":r["rationale"]})
        for r in ContradictionEngine(self.db).list(project_id):
            items.append({"type":"CONTRADICTION","id":r["id"],"priority":"HIGH","title":r["description"],"reason":"Scientific contradiction requires review."})
        for r in KnowledgeImpactEngine(self.db).list(project_id,"PROPOSED"):
            items.append({"type":"IMPACT","id":r["id"],"priority":"NORMAL","title":f"{r['affected_type']}:{r['affected_id']} may be affected","reason":r["reason"]})
        return items

    def approvals(self,limit=100):
        return self.db.all("SELECT * FROM approvals WHERE status='PENDING' ORDER BY created_at DESC LIMIT ?",(int(limit),))
