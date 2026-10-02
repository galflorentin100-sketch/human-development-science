"""Deterministic generator for the next bounded research questions.

It surfaces gaps; it does not decide scientific truth or auto-promote conclusions.
"""
import json
from app.research_queue import ResearchQueue

class ResearchQuestionGenerator:
    def __init__(self,db):
        self.db=db

    def generate(self,project_id):
        if not self.db.one("SELECT id FROM projects WHERE id=?",(project_id,)):
            raise ValueError("project not found")
        candidates=[]
        # Conflicted evidence is an explicit unresolved research gap.
        rows=self.db.all("""SELECT DISTINCT c.id,c.statement
            FROM claims c JOIN evidence e ON e.claim_id=c.id
            WHERE c.project_id=? AND e.verified=1
            GROUP BY c.id,c.statement
            HAVING SUM(CASE WHEN e.status='CONFLICTED' THEN 1 ELSE 0 END)>0""",(project_id,))
        for r in rows:
            candidates.append(("Resolve conflicting evidence for claim: "+r["statement"],
                               "Conflicting evidence was explicitly recorded; investigate the source of disagreement.",
                               "EVIDENCE_CONFLICT",[]))
        # Completed replications that diverge from the source need explicit follow-up,
        # but the generator never labels them as failed/successful from free text.
        if "hds_replication_proposals" in self.db.table_names():
            rows=self.db.all("""SELECT rp.id,rp.replication_question,rp.result
                FROM hds_replication_proposals rp
                WHERE rp.project_id=? AND rp.status='COMPLETED' AND COALESCE(rp.result,'')<>''""",(project_id,))
            for r in rows:
                candidates.append(("Clarify the replication outcome: "+r["replication_question"],
                                   "A replication has a recorded outcome; the structured evidence is insufficient for automatic scientific interpretation.",
                                   "REPLICATION_REVIEW",[r["id"]]))
        # Falsification conclusions are deliberately treated as questions, not verdicts.
        if "hds_falsification_challenges" in self.db.table_names():
            rows=self.db.all("""SELECT id,challenge FROM hds_falsification_challenges
                WHERE project_id=? AND status='COMPLETED'""",(project_id,))
            for r in rows:
                candidates.append(("Follow up on falsification challenge: "+r["challenge"],
                                   "A completed challenge should be independently reviewed before changing a hypothesis or claim.",
                                   "FALSIFICATION_REVIEW",[r["id"]]))
        created=[]
        q=ResearchQueue(self.db)
        for question,rationale,trigger,refs in candidates:
            item=q.propose(project_id,question,rationale,trigger_type="AUTONOMOUS_GAP_DETECTOR",
                           evidence_refs=[x for x in refs if self.db.one("SELECT 1 FROM evidence WHERE id=?",(x,))])
            created.append(item)
        return {"project_id":project_id,"candidates":candidates,"queue_items":created,
                "policy":"gap generation is advisory; no claim, finding, or hypothesis is automatically changed"}

    def explain(self,project_id):
        return self.generate(project_id)
