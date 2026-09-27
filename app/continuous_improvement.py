"""Continuous organizational improvement for HDS.

This layer improves the organization without allowing organizational momentum
to rewrite scientific truth. Improvement proposals are hypotheses until tested.
Scientific claims remain governed by the evidence/claim lifecycle.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid


STATUSES = {"PROPOSED", "EXPERIMENT", "ADOPTED", "REJECTED", "RETIRED"}
AREAS = {"SCIENCE", "PRODUCT", "EDUCATION", "OPERATIONS", "ENGINEERING", "SAFETY"}


def _now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ImprovementProposal:
    id: str
    title: str
    area: str
    hypothesis: str
    success_metric: str
    status: str


class ContinuousImprovementService:
    """OODA-style improvement loop with explicit hypothesis/test/adoption gates."""

    def __init__(self, db):
        self.db = db
    def _require_verified_evidence(self, evidence_ref, con=None):
        if not str(evidence_ref or "").strip():
            raise ValueError("SCIENCE improvements require an evidence reference")
        if con is None:
            row=self.db.one(
                """SELECT e.id,e.verified
                   FROM evidence e
                   WHERE e.id=?
                     AND e.verified=1
                     AND EXISTS (
                       SELECT 1 FROM evidence_reviews r
                       WHERE r.evidence_id=e.id AND r.verdict='VERIFIED'
                     )
                     AND NOT EXISTS (
                       SELECT 1 FROM evidence_reviews r
                       WHERE r.evidence_id=e.id AND r.verdict IN ('REJECTED','CONFLICTED')
                     )""",
                (str(evidence_ref),))
        else:
            row=con.execute(
                """SELECT e.id,e.verified
                   FROM evidence e
                   WHERE e.id=?
                     AND e.verified=1
                     AND EXISTS (
                       SELECT 1 FROM evidence_reviews r
                       WHERE r.evidence_id=e.id AND r.verdict='VERIFIED'
                     )
                     AND NOT EXISTS (
                       SELECT 1 FROM evidence_reviews r
                       WHERE r.evidence_id=e.id AND r.verdict IN ('REJECTED','CONFLICTED')
                     )""",
                (str(evidence_ref),)).fetchone()
        if not row:
            raise ValueError("SCIENCE improvement evidence must be independently verified and non-conflicted")
        return True


    def propose(self, title, area, hypothesis, success_metric, owner, evidence_ref=None):
        if area not in AREAS:
            raise ValueError("invalid improvement area")
        if area == "SCIENCE":
            self._require_verified_evidence(evidence_ref)
        if not all(str(x).strip() for x in (title, hypothesis, success_metric, owner)):
            raise ValueError("title, hypothesis, success_metric and owner are required")
        ident = str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO improvement_proposals
            (id,title,area,hypothesis,success_metric,status,owner,evidence_ref,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (ident,title,area,hypothesis,success_metric,"PROPOSED",owner,evidence_ref,_now()),
        )
        return self.get(ident)

    def start_experiment(self, proposal_id, experiment_design, baseline_note, owner):
        if not str(experiment_design or "").strip() or not str(baseline_note or "").strip():
            raise ValueError("experiment design and baseline are required")
        if not str(owner or "").strip():
            raise ValueError("owner is required")
        with self.db.transaction() as con:
            p=con.execute("SELECT * FROM improvement_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not p:
                raise ValueError("improvement proposal not found")
            p=dict(p)
            if p["status"] != "PROPOSED":
                raise ValueError("only PROPOSED improvements can start an experiment")
            if p["area"] == "SCIENCE":
                self._require_verified_evidence(con, p["evidence_ref"])
            updated=con.execute(
                """UPDATE improvement_proposals
                SET status='EXPERIMENT', experiment_design=?, baseline_note=?, updated_at=?
                WHERE id=? AND status='PROPOSED'""",
                (experiment_design,baseline_note,_now(),proposal_id),
            )
            if updated.rowcount != 1:
                raise ValueError("improvement proposal changed concurrently")
        return self.get(proposal_id)

    def record_result(self, proposal_id, result, outcome_note, evidence_ref=None):
        if result not in {"SUPPORTED","NOT_SUPPORTED","INCONCLUSIVE"}:
            raise ValueError("invalid experiment result")
        if not str(outcome_note or "").strip():
            raise ValueError("outcome note is required")
        with self.db.transaction() as con:
            p=con.execute("SELECT * FROM improvement_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not p:
                raise ValueError("improvement proposal not found")
            if p["status"] != "EXPERIMENT":
                raise ValueError("only active experiments can record results")
            retained_evidence_ref = evidence_ref if evidence_ref is not None else p["evidence_ref"]
            if p["area"] == "SCIENCE":
                retained_evidence_ref = self._require_verified_evidence(con, retained_evidence_ref)
            updated=con.execute(
                """UPDATE improvement_proposals
                SET experiment_result=?, outcome_note=?, evidence_ref=?, updated_at=?
                WHERE id=? AND status='EXPERIMENT'""",
                (result,outcome_note,retained_evidence_ref,_now(),proposal_id),
            )
            if updated.rowcount != 1:
                raise ValueError("improvement proposal changed concurrently")
        return self.get(proposal_id)

    def adopt(self, proposal_id, actor, rationale):
        if not str(actor or "").strip() or not str(rationale or "").strip():
            raise ValueError("actor and adoption rationale are required")
        with self.db.transaction() as con:
            p=con.execute("SELECT * FROM improvement_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not p:
                raise ValueError("improvement proposal not found")
            if p["status"] != "EXPERIMENT":
                raise ValueError("only tested improvements can be adopted")
            if p["experiment_result"] != "SUPPORTED":
                raise ValueError("only supported experiments can be adopted")
            if p["area"] == "SCIENCE":
                self._require_verified_evidence(con, p["evidence_ref"])
            updated=con.execute(
                """UPDATE improvement_proposals
                SET status='ADOPTED', adopted_by=?, adoption_rationale=?, updated_at=?
                WHERE id=? AND status='EXPERIMENT' AND experiment_result='SUPPORTED'""",
                (actor,rationale,_now(),proposal_id),
            )
            if updated.rowcount != 1:
                raise ValueError("improvement proposal changed concurrently")
        return self.get(proposal_id)

    def retire(self, proposal_id, actor, rationale):
        if not str(actor or "").strip() or not str(rationale or "").strip():
            raise ValueError("actor and retirement rationale are required")
        with self.db.transaction() as con:
            p=con.execute("SELECT * FROM improvement_proposals WHERE id=?",(proposal_id,)).fetchone()
            if not p:
                raise ValueError("improvement proposal not found")
            if p["status"] in {"RETIRED","REJECTED"}:
                raise ValueError("improvement proposal is already closed")
            updated=con.execute(
                """UPDATE improvement_proposals
                SET status='RETIRED', retired_by=?, retirement_rationale=?, updated_at=?
                WHERE id=? AND status NOT IN ('RETIRED','REJECTED')""",
                (actor,rationale,_now(),proposal_id),
            )
            if updated.rowcount != 1:
                raise ValueError("improvement proposal changed concurrently")
        return self.get(proposal_id)

    def get(self, proposal_id):
        return self._require(proposal_id)

    def backlog(self, area=None):
        if area is not None and area not in AREAS:
            raise ValueError("invalid improvement area")
        if area:
            return self.db.all("SELECT * FROM improvement_proposals WHERE area=? ORDER BY created_at DESC",(area,))
        return self.db.all("SELECT * FROM improvement_proposals ORDER BY created_at DESC")

    def _require(self, proposal_id):
        row = self.db.one("SELECT * FROM improvement_proposals WHERE id=?",(proposal_id,))
        if not row:
            raise ValueError("improvement proposal not found")
        return row


    def health(self):
        rows=self.db.all("SELECT status,COUNT(*) AS count FROM improvement_proposals GROUP BY status")
        counts={str(r["status"]):int(r["count"]) for r in rows}
        return {"counts":counts,"total":sum(counts.values()),"active_experiments":counts.get("EXPERIMENT",0),"adopted":counts.get("ADOPTED",0)}
