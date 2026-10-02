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
            HAVING SUM(CASE WHEN EXISTS (
                SELECT 1 FROM evidence_reviews er
                WHERE er.evidence_id=e.id AND UPPER(er.verdict)='CONFLICTED'
            ) THEN 1 ELSE 0 END)>0""",(project_id,))
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
            # Materialize the gap as an OPEN research question so the existing
            # autonomous planner can select it; this does not approve a conclusion.
            existing=self.db.one("SELECT * FROM research_questions WHERE project_id=? AND question=? AND status NOT IN ('RESOLVED','CLOSED')",
                                 (project_id,question))
            if not existing:
                from uuid import uuid4
                from app.models import now
                self.db.execute(
                    "INSERT INTO research_questions(id,project_id,question,status,created_at) VALUES (?,?,?,?,?)",
                    (str(uuid4()),project_id,question,"OPEN",now()))
            item=q.propose(project_id,question,rationale,trigger_type="AUTONOMOUS_GAP_DETECTOR",
                           evidence_refs=[x for x in refs if self.db.one("SELECT 1 FROM evidence WHERE id=?",(x,))])
            created.append(item)
        return {"project_id":project_id,"candidates":candidates,"queue_items":created,
                "policy":"gap generation is advisory; no claim, finding, or hypothesis is automatically changed"}

    def explain(self,project_id):
        return self.generate(project_id)
