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

            # Structured study descriptors are included only when explicitly
            # recorded in this HDS project. They are not inferred from abstracts.
            study_metadata = {}
            for source_id in sorted({x["source_id"] for x in verified}):
                study_metadata[source_id] = self.db.all(
                    """SELECT id,title,design,population,findings
                       FROM studies WHERE source_id=? AND project_id=?
                       ORDER BY created_at,id""",
                    (source_id, project_id),
                )

            # Study outcome records are summarized within each study only.
            # Exact outcome name, unit, observation type and session phase are
            # kept separate; no cross-study pooling or participant-level data
            # are exposed by this evidence-map endpoint.
            study_outcome_summaries = {}
            for source_id, studies in study_metadata.items():
                for study in studies:
                    observations = self.db.all(
                        """SELECT o.outcome_name,o.value,o.unit,o.missing_reason,
                                  o.observation_type,o.participant_id,
                                  COALESCE(ss.phase,'NO_SESSION_LINK') AS phase
                           FROM study_outcomes o
                           LEFT JOIN study_sessions ss ON ss.id=o.session_id
                           WHERE o.study_id=?
                           ORDER BY o.outcome_name,o.unit,o.observation_type,phase,o.recorded_at,o.id""",
                        (study["id"],),
                    )
                    groups = {}
                    for observation in observations:
                        key = (
                            observation["outcome_name"],
                            observation["unit"] or "UNIT_NOT_RECORDED",
                            observation["observation_type"],
                            observation["phase"],
                        )
                        groups.setdefault(key, []).append(observation)

                    summaries = []
                    for (outcome_name, unit, observation_type, phase), items in sorted(groups.items()):
                        values = [float(x["value"]) for x in items if x["value"] is not None]
                        missing = [x for x in items if x["value"] is None]
                        ordered = sorted(values)
                        median = None
                        if ordered:
                            middle = len(ordered) // 2
                            median = (
                                ordered[middle] if len(ordered) % 2
                                else (ordered[middle - 1] + ordered[middle]) / 2
                            )
                        summaries.append({
                            "outcome_name": outcome_name,
                            "unit": unit,
                            "observation_type": observation_type,
                            "phase": phase,
                            "records_total": len(items),
                            "participants_total": len({x["participant_id"] for x in items}),
                            "n_observed": len(values),
                            "n_missing": len(missing),
                            "missing_reasons": {
                                reason: sum(1 for x in missing if (x["missing_reason"] or "NOT_RECORDED") == reason)
                                for reason in sorted({x["missing_reason"] or "NOT_RECORDED" for x in missing})
                            },
                            "minimum": min(values) if values else None,
                            "maximum": max(values) if values else None,
                            "mean": sum(values) / len(values) if values else None,
                            "median": median,
                        })
                    study_outcome_summaries.setdefault(source_id, []).append({
                        "study_id": study["id"],
                        "study_title": study["title"],
                        "outcomes": summaries,
                    })

            # Comparison is deliberately literal: values are not normalized,
            # ranked, or interpreted as comparable effect estimates.
            comparison_fields = {}
            for field in ("design", "population", "findings"):
                recorded = []
                missing_source_ids = []
                for source_id in sorted({x["source_id"] for x in verified}):
                    studies = study_metadata.get(source_id, [])
                    if not studies:
                        missing_source_ids.append(source_id)
                    for study in studies:
                        value = study.get(field)
                        if value is None or not str(value).strip():
                            continue
                        recorded.append({
                            "source_id": source_id,
                            "study_id": study["id"],
                            "study_title": study["title"],
                            "value": value,
                        })
                comparison_fields[field] = {
                    "recorded_values": recorded,
                    "distinct_literal_values": len({str(x["value"]).strip() for x in recorded}),
                    "verified_sources_without_study_record": missing_source_ids,
                    "status": "RECORDED_VALUES_PRESENT" if recorded else "NO_RECORDED_VALUES",
                }

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
                "study_comparison": comparison_fields,
                "recorded_study_outcomes": [
                    {"source_id": source_id, "studies": studies}
                    for source_id, studies in sorted(study_outcome_summaries.items())
                ],
                "recorded_study_descriptors": [
                    {
                        "source_id": source_id,
                        "studies": study_metadata[source_id],
                    }
                    for source_id in sorted(study_metadata)
                    if study_metadata[source_id]
                ],
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
