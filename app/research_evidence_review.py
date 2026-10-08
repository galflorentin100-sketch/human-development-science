"""Finalize evidence-audit agent runs through the governed EvidencePipeline."""
import json
from app.evidence_pipeline import EvidencePipeline

class ResearchEvidenceReviewService:
    VALID={"VERIFIED","REJECTED","UNCERTAIN","CONFLICTED"}

    def __init__(self,db):
        self.db=db
        self.pipeline=EvidencePipeline(db)

    def finalize(self,agent_run_id,actor="system"):
        run=self.db.one("SELECT * FROM agent_runs WHERE id=?",(agent_run_id,))
        if not run: raise ValueError("agent run not found")
        task=self.db.one("SELECT * FROM research_evidence_review_tasks WHERE task_id=?",(run["task_id"],))
        if not task: raise ValueError("research evidence review task not found")
        payload=self._parse(run["output_payload"])
        result=payload.get("result",payload)
        if isinstance(result,str):
            try: result=json.loads(result)
            except (TypeError,ValueError): result={}
        if not isinstance(result,dict): raise ValueError("evidence review output must be a JSON object")
        verdict=str(result.get("verdict") or "").upper().strip()
        rationale=str(result.get("rationale") or "").strip()
        if verdict not in self.VALID: raise ValueError("invalid evidence review verdict")
        if not rationale: raise ValueError("evidence review rationale is required")
        review=self.pipeline.review(task["evidence_id"],str(run["agent_id"]),verdict,rationale)
        self.db.execute("UPDATE research_evidence_review_tasks SET status='COMPLETED',completed_at=? WHERE task_id=?",(review["created_at"],run["task_id"]))
        return {"evidence_id":task["evidence_id"],"review":review,"agent_run_id":agent_run_id}

    def _parse(self,raw):
        try: payload=json.loads(raw or "{}")
        except (TypeError,ValueError) as exc: raise ValueError("agent output_payload is not valid JSON") from exc
        if not isinstance(payload,dict): raise ValueError("agent output_payload must be a JSON object")
        return payload
