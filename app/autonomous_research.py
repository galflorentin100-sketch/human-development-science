"""Autonomous research and improvement planner.

It ranks *proposed work*, never scientific truth. It is intentionally read-only.
"""
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc).isoformat()

class AutonomousResearchPlanner:
    def __init__(self,db):
        self.db=db

    def next_work(self):
        candidates=[]
        from app.self_audit import SelfAuditEngine
        audit=SelfAuditEngine(self.db).run()
        for f in audit["findings"]:
            candidates.append({"kind":"AUDIT","priority":100 if f["severity"]=="HIGH" else 70,"title":f["message"],"entity_id":f["entity_id"],"reason":f["kind"]})
        for q in self.db.all("SELECT id,question,status FROM research_questions WHERE status NOT IN ('RESOLVED','CLOSED') ORDER BY created_at ASC LIMIT 20"):
            candidates.append({"kind":"RESEARCH","priority":60,"title":q["question"],"entity_id":q["id"],"reason":"open research question"})
        for p in self.db.all("SELECT id,title,area,status FROM improvement_proposals WHERE status='PROPOSED' ORDER BY created_at ASC LIMIT 20"):
            candidates.append({"kind":"IMPROVEMENT","priority":50,"title":p["title"],"entity_id":p["id"],"reason":"unstarted improvement proposal"})
        for d in self.db.all("SELECT id,decision,status FROM organizational_decisions WHERE status='OPEN' ORDER BY created_at ASC LIMIT 20"):
            candidates.append({"kind":"DECISION_REVIEW","priority":40,"title":d["decision"],"entity_id":d["id"],"reason":"decision awaiting outcome review"})
        candidates.sort(key=lambda x:(-x["priority"],x["kind"],x["entity_id"]))
        return {"generated_at":_now(),"candidate_count":len(candidates),"next":candidates[:10],"selection_policy":"risk_and_evidence_gaps_first; no automatic state mutation"}

    def explain(self, item):
        return {"item":item,"policy":"Planner proposes work only. Human/authorized execution must pass normal permissions, approval, cost and scientific gates."}
