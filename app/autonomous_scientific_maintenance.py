"""Turn scientific maintenance signals into bounded autonomous research proposals."""
from uuid import uuid4
from app.models import now

class AutonomousScientificMaintenance:
    def __init__(self,db): self.db=db

    def propose(self):
        from app.knowledge_freshness import KnowledgeFreshness
        from app.knowledge_impact import KnowledgeImpactAnalyzer
        freshness=KnowledgeFreshness(self.db).scan()
        contradictions=KnowledgeImpactAnalyzer(self.db).contradiction_scan()
        proposals=[]
        for x in freshness["stale"]:
            proposals.append(self._proposal("REVALIDATION",x["entity_type"],x["entity_id"],"Scheduled scientific revalidation is due","Re-review current evidence and downstream dependencies before retaining the current knowledge status."))
        for x in contradictions["impacts"]:
            proposals.append(self._proposal("CONTRADICTION_REVIEW","CLAIM",x["claim_id"],x["reason"],"Resolve evidence conflict and inspect downstream interventions and training protocols."))
        return {"count":len(proposals),"proposals":proposals,"policy":"proposal only; execution requires normal task, permission, approval, cost and scientific gates"}

    def _proposal(self,kind,entity_type,entity_id,reason,success):
        return {"id":str(uuid4()),"kind":kind,"entity_type":entity_type,"entity_id":entity_id,
                "title":f"{kind}: {entity_type} {entity_id}","reason":reason,
                "success_criteria":success,"priority":"HIGH","status":"PROPOSED","created_at":now()}
