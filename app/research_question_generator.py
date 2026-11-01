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
        # Explicit limitations and uncertainty recorded in prior syntheses are
        # high-value follow-up signals. We do not interpret their prose as facts:
        # the proposal asks a researcher to investigate the documented limitation.
        synthesis_rows=self.db.all("""
            SELECT rw.id AS workspace_id,rw.question,rs.id AS synthesis_id,
                   rs.limitations,rs.uncertainty
            FROM research_workspaces rw
            JOIN research_syntheses rs ON rs.workspace_id=rw.id
            WHERE rw.project_id=?
              AND (TRIM(COALESCE(rs.limitations,''))<>'' OR TRIM(COALESCE(rs.uncertainty,''))<>'')
            ORDER BY rs.created_at DESC
            LIMIT 20
        """,(project_id,))
        for r in synthesis_rows:
            details=[]
            if str(r.get("limitations") or "").strip():
                details.append("Recorded limitations: "+str(r["limitations"]).strip()[:1200])
            if str(r.get("uncertainty") or "").strip():
                details.append("Recorded uncertainty: "+str(r["uncertainty"]).strip()[:1200])
            candidates.append((
                "Investigate methodological limitations and uncertainty in: "+str(r["question"])[:300],
                "A prior synthesis explicitly recorded limitations or uncertainty. This is a follow-up prompt, not an assertion that the synthesis is correct. "+" ".join(details),
                "SYNTHESIS_LIMITATION_REVIEW",
                []
            ))

        # A completed retrieval with no results is a search-design gap, not
        # evidence that the topic has no literature.
        retrieval_rows=self.db.all("""
            SELECT rw.id AS workspace_id,rw.question,rr.id AS retrieval_id,
                   rr.status,rr.result_count,rr.error
            FROM research_workspaces rw
            JOIN research_retrieval_runs rr ON rr.workspace_id=rw.id
            WHERE rw.project_id=? AND rr.status IN ('COMPLETED','PARTIAL','FAILED')
              AND COALESCE(rr.result_count,0)=0
            ORDER BY rr.created_at DESC
            LIMIT 20
        """,(project_id,))
        for r in retrieval_rows:
            reason="A literature search returned zero records; this does not establish absence of evidence."
            if str(r.get("error") or "").strip():
                reason+=" Retrieval reported: "+str(r["error"]).strip()[:1000]
            candidates.append((
                "Revise and broaden the literature search for: "+str(r["question"])[:300],
                reason+" Check terminology, synonyms, databases, date coverage, and provider errors before drawing conclusions.",
                "RETRIEVAL_GAP",
                []
            ))

        # Persist routing metadata on research questions so the planner can make
        # deterministic strategy-aware selections without parsing prose.
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
                    "INSERT INTO research_questions(id,project_id,question,status,trigger_type,priority,created_at) VALUES (?,?,?,?,?,?,?)",
                    (str(uuid4()),project_id,question,"OPEN",trigger,
                     85 if trigger in {"FALSIFICATION_REVIEW","REPLICATION_REVIEW"} else (75 if trigger == "SYNTHESIS_LIMITATION_REVIEW" else (70 if trigger == "RETRIEVAL_GAP" else 60)),now()))
            item=q.propose(project_id,question,rationale,trigger_type="AUTONOMOUS_GAP_DETECTOR",
                           evidence_refs=[x for x in refs if self.db.one("SELECT 1 FROM evidence WHERE id=?",(x,))])
            created.append(item)
        return {"project_id":project_id,"candidates":candidates,"queue_items":created,
                "policy":"gap generation is advisory; no claim, finding, or hypothesis is automatically changed"}

    def explain(self,project_id):
        return self.generate(project_id)
