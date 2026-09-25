"""Static integrity checks for scientific state.

Checks consistency and provenance; it does not decide whether a claim is true.
"""
class ScientificIntegrityChecker:
    def __init__(self, db):
        self.db = db

    def project(self, project_id):
        issues = []

        for row in self.db.all(
            "SELECT id,status FROM claims WHERE project_id=? AND status='SUPPORTED'",
            (project_id,),
        ):
            evidence = self.db.all(
                "SELECT id FROM evidence WHERE claim_id=?", (row["id"],)
            )
            if not evidence:
                issues.append({"severity":"CRITICAL","type":"SUPPORTED_CLAIM_WITHOUT_EVIDENCE","id":row["id"]})

        for row in self.db.all(
            "SELECT id,classification,status,evidence_refs FROM research_findings WHERE project_id=?",
            (project_id,),
        ):
            refs = __import__("json").loads(row["evidence_refs"] or "[]")
            if row["status"] == "ACCEPTED" and not refs:
                issues.append({"severity":"CRITICAL","type":"ACCEPTED_FINDING_WITHOUT_EVIDENCE","id":row["id"]})

        for row in self.db.all(
            "SELECT id,status FROM interventions WHERE project_id=? AND status='SUPPORTED'",
            (project_id,),
        ):
            count = self.db.one(
                "SELECT COUNT(*) n FROM intervention_evidence WHERE intervention_id=?",
                (row["id"],),
            )
            if int(count["n"]) == 0:
                issues.append({"severity":"CRITICAL","type":"SUPPORTED_INTERVENTION_WITHOUT_EVIDENCE","id":row["id"]})

        return {
            "project_id": project_id,
            "integrity": "PASS" if not issues else "REVIEW_REQUIRED",
            "issues": issues,
        }
