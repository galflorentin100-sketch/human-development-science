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

    def propose(self, title, area, hypothesis, success_metric, owner, evidence_ref=None):
        if area not in AREAS:
            raise ValueError("invalid improvement area")
        if not all(str(x).strip() for x in (title, hypothesis, success_metric, owner)):
            raise ValueError("title, hypothesis, success_metric and owner are required")
        ident = str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO improvement_proposals
            (id,title,area,hypothesis,success_metric,status,owner,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (ident,title,area,hypothesis,success_metric,"PROPOSED",owner,_now()),
        )
        return self.get(ident)

    def start_experiment(self, proposal_id, experiment_design, baseline_note, owner):
        p = self._require(proposal_id)
        if p["status"] != "PROPOSED":
            raise ValueError("only PROPOSED improvements can start an experiment")
        if not experiment_design.strip() or not baseline_note.strip():
            raise ValueError("experiment design and baseline are required")
        if p["area"] == "SCIENCE" and not p["evidence_ref"]:
            raise ValueError("SCIENCE improvements require an evidence reference or explicit research basis")
        self.db.execute(
            """UPDATE improvement_proposals
            SET status='EXPERIMENT', experiment_design=?, baseline_note=?, updated_at=?
            WHERE id=?""",
            (experiment_design,baseline_note,_now(),proposal_id),
        )
        return self.get(proposal_id)

    def record_result(self, proposal_id, result, outcome_note, evidence_ref=None):
        p = self._require(proposal_id)
        if p["status"] != "EXPERIMENT":
            raise ValueError("only active experiments can record results")
        if result not in {"SUPPORTED","NOT_SUPPORTED","INCONCLUSIVE"}:
            raise ValueError("invalid experiment result")
        if not str(outcome_note).strip():
            raise ValueError("outcome note is required")
        self.db.execute(
            """UPDATE improvement_proposals
            SET experiment_result=?, outcome_note=?, evidence_ref=?, updated_at=?
            WHERE id=?""",
            (result,outcome_note,evidence_ref,_now(),proposal_id),
        )
        return self.get(proposal_id)

    def adopt(self, proposal_id, actor, rationale):
        p = self._require(proposal_id)
        if p["status"] != "EXPERIMENT":
            raise ValueError("only tested improvements can be adopted")
        if p["experiment_result"] != "SUPPORTED":
            raise ValueError("only supported experiments can be adopted")
        if not rationale.strip():
            raise ValueError("adoption rationale is required")
        self.db.execute(
            """UPDATE improvement_proposals
            SET status='ADOPTED', adopted_by=?, adoption_rationale=?, updated_at=?
            WHERE id=?""",
            (actor,rationale,_now(),proposal_id),
        )
        return self.get(proposal_id)

    def retire(self, proposal_id, actor, rationale):
        p = self._require(proposal_id)
        if not rationale.strip():
            raise ValueError("retirement rationale is required")
        self.db.execute(
            """UPDATE improvement_proposals
            SET status='RETIRED', retired_by=?, retirement_rationale=?, updated_at=?
            WHERE id=?""",
            (actor,rationale,_now(),proposal_id),
        )
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
