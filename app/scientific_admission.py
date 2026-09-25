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
        rows=self.db.all("SELECT id FROM evidence WHERE claim_id=?",(claim_id,))
        states=[EvidencePipeline(self.db).resolve(r["id"])["state"] for r in rows]
        verified=sum(s=="VERIFIED" for s in states)
        conflicts=sum(s=="CONFLICTED" for s in states)
        return {"claim":claim,"evidence_count":len(states),"verified_evidence":verified,"conflicts":conflicts,
                "supported":claim["status"]=="SUPPORTED" and verified>0 and conflicts==0}

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
