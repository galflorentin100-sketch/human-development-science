"""Adapters from governed agent output into research review records."""
import json

class ResearchReviewAgentAdapter:
    def __init__(self,db): self.db=db

    def finalize(self,review_id,actor):
        review=self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))
        if not review or review["status"]!="ACCEPTED":
            raise ValueError("accepted agent output review required")
        link=self.db.one("SELECT * FROM research_review_tasks WHERE task_id=?",(review["task_id"],))
        if not link: raise ValueError("research review task mapping not found")
        run=self.db.one("SELECT * FROM agent_runs WHERE id=?",(review["agent_run_id"],))
        payload=json.loads(run["output_payload"] or "{}")
        result=payload.get("result") or payload.get("output") or payload
        if isinstance(result,str):
            result={"summary":result}
        role=link["role"]
        if role=="skeptic":
            from app.skeptic import SkepticService
            existing=self.db.one("SELECT id FROM research_skeptic_reviews WHERE workspace_id=? AND synthesis_id=? ORDER BY created_at DESC LIMIT 1",(link["workspace_id"],link["synthesis_id"]))
            row=SkepticService(self.db).get(existing["id"]) if existing else SkepticService(self.db).create(link["workspace_id"],link["synthesis_id"],None)
            if row["status"]=="READY_FOR_REVIEW":
                SkepticService(self.db).record(row["id"],result.get("objections",[]),result.get("missing_evidence",[]),result.get("alternative_explanations",[]))
            return SkepticService(self.db).get(row["id"])
        if role=="evidence-auditor":
            from app.research_evidence_auditor import ResearchEvidenceAuditor
            return ResearchEvidenceAuditor(self.db).audit_synthesis(link["synthesis_id"],actor)
        raise ValueError("unsupported research review role")
