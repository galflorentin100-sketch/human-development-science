"""Static integrity checks for scientific state.

Checks consistency and provenance; it does not decide whether a claim is true.
"""
import json

class ScientificIntegrityChecker:
    def __init__(self, db):
        self.db = db

    def project(self, project_id):
        if not self.db.one("SELECT 1 FROM projects WHERE id=?", (project_id,)):
            raise ValueError("project not found")
        issues = []

        from app.evidence_pipeline import EvidencePipeline
        pipeline = EvidencePipeline(self.db)

        for row in self.db.all(
            "SELECT id,status FROM claims WHERE project_id=? AND status='SUPPORTED'",
            (project_id,),
        ):
            evidence = self.db.all(
                "SELECT id,stance FROM evidence WHERE claim_id=?", (row["id"],)
            )
            if not evidence:
                issues.append({"severity":"CRITICAL","type":"SUPPORTED_CLAIM_WITHOUT_EVIDENCE","id":row["id"]})
                continue
            states = [pipeline.resolve(e["id"]) for e in evidence]
            verified_support = sum(
                1 for item in states
                if item["state"] == "VERIFIED" and item["stance"] == "SUPPORTS"
            )
            verified_contradict = sum(
                1 for item in states
                if item["state"] == "VERIFIED" and item["stance"] == "CONTRADICTS"
            )
            conflicted = any(item["state"] == "CONFLICTED" for item in states)
            if verified_support == 0:
                issues.append({"severity":"CRITICAL","type":"SUPPORTED_CLAIM_WITHOUT_VERIFIED_SUPPORT","id":row["id"]})
            if verified_contradict > 0 or conflicted:
                issues.append({"severity":"CRITICAL","type":"SUPPORTED_CLAIM_WITH_CONFLICTING_EVIDENCE","id":row["id"]})

        for row in self.db.all(
            "SELECT id,status,evidence_refs FROM research_findings WHERE project_id=?",
            (project_id,),
        ):
            try:
                refs = json.loads(row["evidence_refs"] or "[]")
            except (TypeError, ValueError):
                refs = []
                issues.append({"severity":"CRITICAL","type":"FINDING_WITH_INVALID_EVIDENCE_REFS","id":row["id"]})
            if row["status"] == "ACCEPTED":
                if not refs:
                    issues.append({"severity":"CRITICAL","type":"ACCEPTED_FINDING_WITHOUT_EVIDENCE","id":row["id"]})
                for ref in refs:
                    evidence = self.db.one(
                        "SELECT e.id,c.project_id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=?",
                        (str(ref),),
                    )
                    if not evidence or str(evidence["project_id"]) != str(project_id):
                        issues.append({"severity":"CRITICAL","type":"ACCEPTED_FINDING_WITH_INVALID_EVIDENCE","id":row["id"]})
                        continue
                    state = pipeline.resolve(str(ref))
                    if state["state"] != "VERIFIED":
                        issues.append({"severity":"CRITICAL","type":"ACCEPTED_FINDING_WITH_UNVERIFIED_EVIDENCE","id":row["id"]})

        for row in self.db.all(
            "SELECT id,status FROM interventions WHERE project_id=? AND status='SUPPORTED'",
            (project_id,),
        ):
            refs = self.db.all(
                "SELECT evidence_ref FROM intervention_evidence WHERE intervention_id=?",
                (row["id"],)
            )
            if not refs:
                issues.append({"severity":"CRITICAL","type":"SUPPORTED_INTERVENTION_WITHOUT_EVIDENCE","id":row["id"]})
                continue
            states = []
            for ref in refs:
                try:
                    state = pipeline.resolve(str(ref["evidence_ref"]))
                except ValueError:
                    state = {"state":"MISSING"}
                states.append(state["state"])
            if any(state != "VERIFIED" for state in states):
                issues.append({"severity":"CRITICAL","type":"SUPPORTED_INTERVENTION_WITHOUT_VERIFIED_EVIDENCE","id":row["id"]})
            if "CONFLICTED" in states:
                issues.append({"severity":"CRITICAL","type":"SUPPORTED_INTERVENTION_WITH_CONFLICTING_EVIDENCE","id":row["id"]})

        return {
            "project_id": project_id,
            "integrity": "PASS" if not issues else "REVIEW_REQUIRED",
            "issues": issues,
        }
