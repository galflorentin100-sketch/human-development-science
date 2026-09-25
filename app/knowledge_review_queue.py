"""Review queue generated from scientific knowledge impacts."""
from uuid import uuid4
from app.models import now

class KnowledgeReviewQueue:
    def __init__(self,db): self.db=db

    def generate(self):
        from app.knowledge_impact import KnowledgeImpactAnalyzer
        scan=KnowledgeImpactAnalyzer(self.db).contradiction_scan()
        queue=[]
        for item in scan["impacts"]:
            queue.append({"id":str(uuid4()),"claim_id":item["claim_id"],"reason":item["reason"],"priority":"HIGH","status":"PROPOSED","created_at":now(),
                          "required_actions":["review_evidence","review_claim","inspect_downstream_training","inspect_downstream_decisions"]})
        return {"count":len(queue),"items":queue,"policy":"review proposals only; no automatic downgrade"}
