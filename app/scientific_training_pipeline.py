"""End-to-end scientific-to-training provenance graph.

Links the chain without upgrading evidence:
source/evidence -> finding -> claim -> intervention -> training protocol -> sessions.
Every edge is explicit and auditable.

Important: provenance establishes traceability only; it does not establish causal efficacy.
"""
from app.evidence_pipeline import EvidencePipeline


class ScientificTrainingPipeline:
    def __init__(self, db):
        self.db = db

    def trace(self, protocol_id):
        p = self.db.one("SELECT * FROM training_protocols WHERE id=?", (protocol_id,))
        if not p:
            raise ValueError("training protocol not found")

        result = {
            "protocol": p,
            "intervention": None,
            "claim": None,
            "evidence": [],
            "finding_links": [],
            "sessions": [],
        }

        # Direct protocol evidence is part of the provenance chain too.
        pipe = EvidencePipeline(self.db)
        for e in self.db.all(
            "SELECT * FROM training_protocol_evidence WHERE protocol_id=? ORDER BY created_at",
            (protocol_id,),
        ):
            try:
                resolution = pipe.resolve(e["evidence_ref"])
            except ValueError:
                resolution = {
                    "evidence_id": e["evidence_ref"],
                    "state": "MISSING",
                }
            result["evidence"].append(
                {"layer": "TRAINING_PROTOCOL", "record": e, "resolution": resolution}
            )

        if p["intervention_id"]:
            result["intervention"] = self.db.one(
                "SELECT * FROM interventions WHERE id=?", (p["intervention_id"],)
            )
            if result["intervention"]:
                for e in self.db.all(
                    "SELECT * FROM intervention_evidence WHERE intervention_id=? ORDER BY created_at",
                    (p["intervention_id"],),
                ):
                    try:
                        resolution = pipe.resolve(e["evidence_ref"])
                    except ValueError:
                        resolution = {
                            "evidence_id": e["evidence_ref"],
                            "state": "MISSING",
                        }
                    result["evidence"].append(
                        {"layer": "INTERVENTION", "record": e, "resolution": resolution}
                    )

        if p["source_claim_id"]:
            result["claim"] = self.db.one(
                "SELECT * FROM claims WHERE id=?", (p["source_claim_id"],)
            )
            if result["claim"]:
                rows = self.db.all(
                    "SELECT * FROM evidence WHERE claim_id=? ORDER BY created_at",
                    (p["source_claim_id"],),
                )
                for e in rows:
                    result["evidence"].append(
                        {
                            "layer": "CLAIM",
                            "record": e,
                            "resolution": pipe.resolve(e["id"]),
                        }
                    )
                result["finding_links"] = self.db.all(
                    "SELECT * FROM research_findings "
                    "WHERE project_id=(SELECT project_id FROM claims WHERE id=?) "
                    "ORDER BY created_at DESC",
                    (p["source_claim_id"],),
                )

        # Sessions are downstream observations of protocol execution.
        result["sessions"] = self.db.all(
            "SELECT * FROM training_sessions WHERE protocol_id=? ORDER BY session_number, created_at",
            (protocol_id,),
        )

        return result

    def readiness(self, protocol_id):
        graph = self.trace(protocol_id)
        p = graph["protocol"]
        blockers = []

        if not (p["source_claim_id"] or p["intervention_id"]):
            blockers.append("no_scientific_basis")
        if p["source_claim_id"] and not graph["claim"]:
            blockers.append("source_claim_missing")
        if p["intervention_id"] and not graph["intervention"]:
            blockers.append("intervention_missing")

        verified = sum(
            1
            for x in graph["evidence"]
            if x.get("resolution", {}).get("state") == "VERIFIED"
        )
        conflicts = sum(
            1
            for x in graph["evidence"]
            if x.get("resolution", {}).get("state") == "CONFLICTED"
        )
        missing = sum(
            1
            for x in graph["evidence"]
            if x.get("resolution", {}).get("state") == "MISSING"
        )

        if conflicts:
            blockers.append("conflicting_evidence")
        if missing:
            blockers.append("missing_evidence")

        return {
            "protocol_id": protocol_id,
            "ready_for_scientific_review": not blockers,
            "verified_evidence_count": verified,
            "conflicted_evidence_count": conflicts,
            "missing_evidence_count": missing,
            "session_count": len(graph["sessions"]),
            "blockers": blockers,
            "principle": "provenance supports traceability; it does not by itself establish causal efficacy",
        }
