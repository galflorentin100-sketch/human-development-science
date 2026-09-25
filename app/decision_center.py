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
                items.append({"type":"RESEARCH","id":r["id"],"priority":r["priority"],"title":r["question"],
                              "reason":r["rationale"],"trigger_type":r.get("trigger_type","MANUAL"),
                              "status":r["status"]})
        for r in ContradictionEngine(self.db).list(project_id):
            items.append({"type":"CONTRADICTION","id":r["id"],"priority":"HIGH","title":r["description"],"reason":"Scientific contradiction requires review."})
        for r in KnowledgeImpactEngine(self.db).list(project_id,"PROPOSED"):
            items.append({"type":"IMPACT","id":r["id"],"priority":"NORMAL","title":f"{r['affected_type']}:{r['affected_id']} may be affected","reason":r["reason"]})
        # Surface accepted agent-output reviews as a distinct founder decision:
        # conversion into a finding is still gated and never automatic.
        for r in self.db.all("SELECT * FROM agent_output_reviews WHERE project_id=? AND status='ACCEPTED' ORDER BY created_at DESC",(project_id,)):
            existing=self.db.one("SELECT id,status FROM research_findings WHERE project_id=? AND source_type='AGENT_OUTPUT' AND source_id=? LIMIT 1",(project_id,r["agent_run_id"]))
            if not existing:
                items.append({"type":"AGENT_OUTPUT","id":r["id"],"priority":"HIGH",
                              "title":f"Review accepted agent output {r['id']}",
                              "reason":"Accepted output is eligible for candidate-finding creation; human decision remains required."})
        for r in self.db.all("SELECT * FROM research_findings WHERE project_id=? AND status='CANDIDATE' ORDER BY created_at DESC",(project_id,)):
            items.append({"type":"FINDING","id":r["id"],"priority":"HIGH",
                          "title":r["statement"],"reason":"Candidate finding requires independent scientific review."})
        for r in self.db.all("SELECT * FROM research_findings WHERE project_id=? AND status='ACCEPTED' ORDER BY reviewed_at DESC",(project_id,)):
            revision=self.db.one("SELECT id,status FROM claim_revisions cr JOIN claims c ON c.id=cr.claim_id WHERE c.project_id=? AND cr.source_finding_id=? LIMIT 1",(project_id,r["id"]))
            if not revision:
                items.append({"type":"ACCEPTED_FINDING","id":r["id"],"priority":"NORMAL",
                              "title":r["statement"],"reason":"Accepted finding can inform a claim revision; explicit claim selection and human approval are required."})
        for item in items:
            item["next_action"]={
                "RESEARCH":"delegate_research",
                "CONTRADICTION":"delegate_skeptic_review",
                "IMPACT":"review_impact",
                "AGENT_OUTPUT":"create_candidate_finding",
                "FINDING":"review_finding","ACCEPTED_FINDING":"propose_claim_revision",
                "EXPERIMENT":"delegate_experiment_design",
                "INTEGRITY":"delegate_evidence_audit",
            }.get(item["type"],"review")
            item["requires_founder_approval"]=item["type"] in {"CONTRADICTION","IMPACT","AGENT_OUTPUT","FINDING","ACCEPTED_FINDING"}
            item["agent_role"]={
                "RESEARCH":"researcher","CONTRADICTION":"skeptic","IMPACT":"knowledge-manager",
                "AGENT_OUTPUT":"knowledge-manager","FINDING":"evidence-auditor","ACCEPTED_FINDING":"founder-advisor","EXPERIMENT":"experiment-designer",
                "INTEGRITY":"evidence-auditor"
            }.get(item["type"],"founder-advisor")
        return items

    def delegateable(self,project_id):
        """Return decisions that have not yet been delegated to an active task."""
        items=self.list(project_id)
        result=[]
        for item in items:
            title=f"[{item['type']}] {item['title']}"
            active=self.db.one(
                "SELECT id,status,owner FROM tasks WHERE project_id=? AND title=? AND status NOT IN ('COMPLETED','CANCELLED')",
                (project_id,title),
            )
            if not active:
                result.append(item)
        return result

    def approvals(self,limit=100):
        return self.db.all("SELECT * FROM approvals WHERE status='PENDING' ORDER BY created_at DESC LIMIT ?",(int(limit),))
