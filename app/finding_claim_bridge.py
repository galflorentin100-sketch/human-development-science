"""Promote reviewed findings into explicit claims without bypassing claim governance."""
import json
from uuid import uuid4
from app.models import now

class FindingClaimBridge:
    def __init__(self,db):
        self.db=db

    def propose_claim(self,finding_id,actor):
        finding=self.db.one("SELECT * FROM research_findings WHERE id=?",(finding_id,))
        if not finding: raise ValueError("finding not found")
        if finding["status"]!="ACCEPTED": raise ValueError("only accepted findings can propose claims")
        refs=json.loads(finding["evidence_refs"] or "[]")
        if not refs: raise ValueError("accepted finding must have evidence references")
        existing=self.db.one("SELECT id FROM claims WHERE statement=? AND project_id=?",(finding["statement"],finding["project_id"]))
        if existing: return {"claim_id":existing["id"],"created":False}
        claim_id=str(uuid4())
        self.db.execute("""INSERT INTO claims
            (id,project_id,statement,classification,evidence_level,confidence,status,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (claim_id,finding["project_id"],finding["statement"],finding["classification"],
             "PRELIMINARY",0.0,"PROPOSED",now()))
        for ref in refs:
            self.db.execute("""INSERT INTO claim_revisions
                (id,claim_id,prior_classification,prior_confidence,new_classification,new_confidence,reason,evidence_id,review_required,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid4()),claim_id,None,None,finding["classification"],0.0,
                 "created from accepted research finding",str(ref),1,now()))
        return {"claim_id":claim_id,"created":True,"status":"PROPOSED","source_finding_id":finding_id,"evidence_refs":refs}
