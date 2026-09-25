"""Turn an accepted, reviewed agent output into a candidate finding.

This service intentionally stops before claim mutation. A human-reviewed output
can produce a finding proposal, but claims require the existing revision gate.
"""
import json, hashlib
from uuid import uuid4
from app.models import now
from app.research import ResearchFindingService

class KnowledgeUpdateProposer:
    def __init__(self,db): self.db=db

    def propose_from_output(self,review_id):
        review=self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))
        if not review: raise ValueError("output review not found")
        if review["status"]!="ACCEPTED": raise ValueError("only accepted outputs can create findings")
        run=self.db.one("SELECT * FROM agent_runs WHERE id=?",(review["agent_run_id"],))
        if not run: raise ValueError("agent run not found")
        existing=self.db.one("SELECT * FROM research_findings WHERE project_id=? AND source_type='AGENT_OUTPUT' AND source_id=? ORDER BY created_at DESC LIMIT 1",(review["project_id"],run["id"]))
        if existing:
            return existing
        payload=json.loads(run["output_payload"] or "{}")
        result=payload.get("payload",{}).get("result") or payload.get("result") or ""
        if not str(result).strip(): raise ValueError("accepted output has no substantive result")
        refs=json.loads(review["evidence_refs"] or "[]")
        provenance={
            "agent_run_id":run["id"],
            "task_id":run["task_id"],
            "output_review_id":review_id,
            "provenance_hash":review["provenance_hash"],
            "evidence_refs":refs
        }
        statement="Candidate finding generated from a human-reviewed agent output; it is not yet a scientific claim."
        finding=ResearchFindingService(self.db).create(
            review["project_id"],statement,
            classification="INFERENCE",
            source_type="AGENT_OUTPUT",
            source_id=run["id"],
            evidence_refs=refs,
            interpretation=json.dumps({"agent_result":result,"provenance":provenance},sort_keys=True),
            created_by="knowledge-update-proposer")
        self.db.audit("scientific.candidate_finding_created","finding",finding["id"],"knowledge-update-proposer",
                      {"review_id":review_id,"agent_run_id":run["id"]},now(),str(uuid4()))
        return finding

    def propose_claim_revision(self,finding_id,claim_id,new_statement,new_status,rationale,evidence_refs=()):
        from app.claim_revision import ClaimRevisionService
        finding=self.db.one("SELECT * FROM research_findings WHERE id=?",(finding_id,))
        if not finding: raise ValueError("finding not found")
        if finding["status"]!="ACCEPTED": raise ValueError("finding must be ACCEPTED before proposing a claim revision")
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        if claim["project_id"]!=finding["project_id"]:
            raise ValueError("finding and claim must belong to the same project")
        finding_refs=set(json.loads(finding["evidence_refs"] or "[]"))
        proposed_refs=set(str(x) for x in evidence_refs)
        if proposed_refs and not proposed_refs.issubset(finding_refs):
            raise ValueError("claim revision evidence must be a subset of the accepted finding evidence")
        if not str(rationale or "").strip():
            raise ValueError("rationale is required")
        revision=ClaimRevisionService(self.db).propose(
            claim_id,new_statement,new_status,rationale,evidence_refs,
            actor="knowledge-update-proposer")
        self.db.audit("scientific.claim_revision_proposed","claim_revision",revision["id"],
                      "knowledge-update-proposer",{"finding_id":finding_id},now(),str(uuid4()))
        return revision
