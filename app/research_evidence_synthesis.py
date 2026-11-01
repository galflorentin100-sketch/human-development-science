"""Deterministic, provenance-linked evidence map for project claims.

This is descriptive bookkeeping, not a meta-analysis or scientific verdict.
Only reviewer-verified evidence is included in the stance counts.
"""
from app.evidence_pipeline import EvidencePipeline


class ResearchEvidenceSynthesizer:
    def __init__(self, db):
        self.db = db

    def synthesize_project(self, project_id):
        if not self.db.one("SELECT id FROM projects WHERE id=?", (project_id,)):
            raise ValueError("project not found")

        claims = self.db.all(
            "SELECT id,statement,classification,evidence_level,status FROM claims WHERE project_id=? ORDER BY created_at,id",
            (project_id,),
        )
        output = []
        pipeline = EvidencePipeline(self.db)
        for claim in claims:
            rows = self.db.all(
                """SELECT e.id AS evidence_id,e.source_id,e.stance,e.excerpt,
                          s.title,s.authors,s.publication_year,s.url
                   FROM evidence e JOIN sources s ON s.id=e.source_id
                   WHERE e.claim_id=? ORDER BY e.created_at,e.id""",
                (claim["id"],),
            )
            verified = []
            excluded = []
            for row in rows:
                state = pipeline.resolve(row["evidence_id"])["state"]
                if state == "VERIFIED":
                    verified.append({**row, "review_state": state})
                else:
                    excluded.append({"evidence_id": row["evidence_id"], "review_state": state})

            support = [x for x in verified if x["stance"] == "SUPPORTS"]
            contradict = [x for x in verified if x["stance"] == "CONTRADICTS"]
            neutral = [x for x in verified if x["stance"] == "NEUTRAL"]
            support_sources = sorted({x["source_id"] for x in support})
            contradict_sources = sorted({x["source_id"] for x in contradict})

            if support and contradict:
                pattern = "MIXED_VERIFIED_STANCES"
                interpretation = "Verified excerpts attached to this claim include both supporting and contradicting stances. This flags disagreement for human examination; it does not resolve it."
            elif len(support_sources) >= 2:
                pattern = "MULTI_SOURCE_SUPPORT"
                interpretation = "At least two distinct sources have reviewer-verified supporting excerpts attached. Independence, study quality, and generalizability have not been assessed."
            elif len(contradict_sources) >= 2:
                pattern = "MULTI_SOURCE_CONTRADICTION"
                interpretation = "At least two distinct sources have reviewer-verified contradicting excerpts attached. Independence, study quality, and generalizability have not been assessed."
            elif len(verified) == 0:
                pattern = "NO_VERIFIED_EVIDENCE"
                interpretation = "No evidence item currently resolves to VERIFIED under the review records. This is not evidence that the claim is false."
            else:
                pattern = "LIMITED_VERIFIED_RECORD"
                interpretation = "The currently verified record is limited or single-sided. This is not a formal assessment of evidence sufficiency."

            output.append({
                "claim_id": claim["id"],
                "claim": claim["statement"],
                "classification": claim["classification"],
                "claim_evidence_level": claim["evidence_level"],
                "claim_status": claim["status"],
                "pattern": pattern,
                "interpretation": interpretation,
                "counts": {
                    "verified_support_excerpts": len(support),
                    "verified_contradict_excerpts": len(contradict),
                    "verified_neutral_excerpts": len(neutral),
                    "distinct_supporting_sources": len(support_sources),
                    "distinct_contradicting_sources": len(contradict_sources),
                    "excluded_nonverified_items": len(excluded),
                },
                "verified_evidence": [
                    {
                        "evidence_id": x["evidence_id"],
                        "source_id": x["source_id"],
                        "source_title": x["title"],
                        "authors": x["authors"],
                        "publication_year": x["publication_year"],
                        "url": x["url"],
                        "stance": x["stance"],
                        "excerpt": x["excerpt"],
                    }
                    for x in verified
                ],
                "excluded_evidence": excluded,
            })

        return {
            "project_id": project_id,
            "claims": output,
            "method": "descriptive stance and distinct-source counts over evidence whose review state resolves to VERIFIED",
            "limitations": [
                "Not a systematic review, meta-analysis, risk-of-bias assessment, or causal inference.",
                "Distinct source records do not guarantee independent research teams or independent datasets.",
                "Excerpt stance labels are reviewer-recorded and may require re-examination in full context.",
                "No automatic claim status, evidence level, finding, or hypothesis is changed.",
            ],
        }
