"""Admission gates between scientific knowledge layers.

A gate checks provenance and evidence state; it never upgrades evidence by itself.
"""
class ScientificAdmissionGate:
    def __init__(self,db):
        self.db=db

    def claim(self,claim_id):
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        from app.evidence_pipeline import EvidencePipeline
        state=EvidencePipeline(self.db).claim_evidence_state(claim_id)
        return {"claim":claim,"evidence_count":len(state["evidence"]),
                "verified_evidence":state["verified_support"],
                "verified_support":state["verified_support"],
                "verified_contradict":state["verified_contradict"],
                "conflicts":state["conflicted"],
                "supported":claim["status"]=="SUPPORTED"
                           and state["verified_support"]>0
                           and state["verified_contradict"]==0
                           and state["conflicted"]==0}

    def intervention(self,intervention_id):
        intervention=self.db.one("SELECT * FROM interventions WHERE id=?",(intervention_id,))
        if not intervention: raise ValueError("intervention not found")
        rows=self.db.all("SELECT evidence_ref,evidence_kind FROM intervention_evidence WHERE intervention_id=?",(intervention_id,))
        from app.evidence_pipeline import EvidencePipeline
        states=[]
        for r in rows:
            try: states.append(EvidencePipeline(self.db).resolve(r["evidence_ref"])["state"])
            except ValueError: states.append("MISSING")
        return {"intervention":intervention,"evidence_count":len(states),
                "verified_evidence":sum(s=="VERIFIED" for s in states),
                "conflicts":sum(s=="CONFLICTED" for s in states),
                "supported":intervention["status"]=="SUPPORTED" and bool(states) and all(s=="VERIFIED" for s in states)}

    def training(self,protocol_id):
        from app.scientific_training_pipeline import ScientificTrainingPipeline
        return ScientificTrainingPipeline(self.db).readiness(protocol_id)

    def assert_training_admissible(self,protocol_id,target_status):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol: raise ValueError("training protocol not found")
        if target_status=="PILOT" and not (protocol["source_claim_id"] or protocol["intervention_id"]):
            raise ValueError("PILOT requires explicit scientific basis")
        if target_status=="SUPPORTED":
            if not (protocol["source_claim_id"] or protocol["intervention_id"]):
                raise ValueError("SUPPORTED requires explicit scientific basis")
            if protocol["source_claim_id"] and not self.claim(protocol["source_claim_id"])["supported"]:
                raise ValueError("SUPPORTED requires a supported claim with verified non-conflicted evidence")
            if protocol["intervention_id"] and not self.intervention(protocol["intervention_id"])["supported"]:
                raise ValueError("SUPPORTED requires a supported intervention with verified non-conflicted evidence")
        return {"admissible":True,"target_status":target_status,"protocol_id":protocol_id}

    def assert_training_operational(self,protocol_id):
        """Block execution when a protocol's scientific basis is no longer admissible."""
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol:
            raise ValueError("training protocol not found")
        if protocol["status"]=="RETIRED":
            raise ValueError("retired training protocols cannot be executed")
        if protocol["status"] not in {"PILOT","SUPPORTED"}:
            raise ValueError("training protocol is not operationally admissible")

        # Experimental PILOT protocols may operate before evidentiary admission.
        # Once SUPPORTED, every attached evidence item must remain independently verified.
        from app.evidence_pipeline import EvidencePipeline
        refs=self.db.all("SELECT evidence_ref FROM training_protocol_evidence WHERE protocol_id=?",(protocol_id,))
        if refs:
            states=[EvidencePipeline(self.db).resolve(ref["evidence_ref"])["state"] for ref in refs]
            # A pilot may proceed with preliminary/uncertain evidence, but an
            # explicit contradiction or evidence conflict is never operationally safe.
            if "CONFLICTED" in states or "REJECTED" in states:
                raise ValueError("training protocol execution blocked by non-verified or conflicted evidence")
            if protocol["status"]=="SUPPORTED" and any(state!="VERIFIED" for state in states):
                raise ValueError("training protocol execution blocked by non-verified or conflicted evidence")
        elif protocol["status"]=="SUPPORTED":
            raise ValueError("training protocol has no attached evidence")

        # Any linked scientific basis must remain project-local. A PILOT may reference
        # a hypothesis; a SUPPORTED protocol must reference a currently supported basis.
        if protocol["source_claim_id"]:
            claim=self.db.one("SELECT project_id,status FROM claims WHERE id=?",(protocol["source_claim_id"],))
            if not claim or str(claim["project_id"])!=str(protocol["project_id"]):
                raise ValueError("training protocol execution blocked because its source claim belongs to another project")
            if protocol["status"]=="SUPPORTED" and not self.claim(protocol["source_claim_id"])["supported"]:
                raise ValueError("training protocol execution blocked because its source claim is no longer supported")
        if protocol["intervention_id"]:
            intervention=self.db.one("SELECT project_id,status FROM interventions WHERE id=?",(protocol["intervention_id"],))
            if not intervention or str(intervention["project_id"])!=str(protocol["project_id"]):
                raise ValueError("training protocol execution blocked because its intervention belongs to another project")
            if protocol["status"]=="SUPPORTED" and not self.intervention(protocol["intervention_id"])["supported"]:
                raise ValueError("training protocol execution blocked because its intervention is no longer supported")

        freshness_checks=[("TRAINING_PROTOCOL",protocol_id)]
        if protocol["source_claim_id"]:
            freshness_checks.append(("CLAIM",protocol["source_claim_id"]))
        if protocol["intervention_id"]:
            freshness_checks.append(("INTERVENTION",protocol["intervention_id"]))
        for entity_type,entity_id in freshness_checks:
            freshness=self.db.all(
                "SELECT status,next_review_at FROM knowledge_freshness WHERE entity_type=? AND entity_id=?",
                (entity_type,entity_id),
            )
            if any(row["status"] in {"STALE","REVIEW_REQUIRED"} or (row["next_review_at"] and row["next_review_at"] < __import__("app.models", fromlist=["now"]).now()) for row in freshness):
                raise ValueError("training protocol execution blocked by stale scientific basis; freshness review required")
        return {"admissible":True,"protocol_id":protocol_id,"status":protocol["status"]}

