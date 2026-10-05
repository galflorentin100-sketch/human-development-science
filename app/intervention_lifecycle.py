"""Lifecycle governance for scientific interventions."""
import json
from uuid import uuid4
from app.models import now

class InterventionLifecycle:
    ALLOWED={"EXPERIMENTAL":{"PILOT","RETIRED"},"PILOT":{"SUPPORTED","RETIRED"},"SUPPORTED":{"RETIRED"},"RETIRED":set()}
    def __init__(self,db): self.db=db

    def promote(self,intervention_id,new_status,actor,rationale):
        row=self.db.one("SELECT * FROM interventions WHERE id=?",(intervention_id,))
        if not row: raise ValueError("intervention not found")
        if new_status not in self.ALLOWED.get(row["status"],set()): raise ValueError(f"invalid intervention transition: {row['status']} -> {new_status}")
        if not str(rationale).strip(): raise ValueError("promotion rationale is required")
        if new_status=="PILOT":
            if not row["dosage"].strip() or not row["population"].strip() or not row["mechanism"].strip():
                raise ValueError("PILOT requires mechanism, dosage and population")
        if new_status=="SUPPORTED":
            from app.evidence_pipeline import EvidencePipeline
            refs=self.db.all("SELECT evidence_ref FROM intervention_evidence WHERE intervention_id=?",(intervention_id,))
            if not refs: raise ValueError("SUPPORTED intervention requires evidence")
            states=[]
            for r in refs:
                try: states.append(EvidencePipeline(self.db).resolve(r["evidence_ref"])["state"])
                except ValueError: states.append("MISSING")
            for ref in refs:
                evidence_row=self.db.one("SELECT e.id,e.claim_id,c.status AS claim_status,c.project_id AS claim_project_id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=?",(str(ref["evidence_ref"]),))
                if not evidence_row:
                    raise ValueError("SUPPORTED intervention requires all attached evidence to exist")
                if row["project_id"] is not None and str(evidence_row["claim_project_id"]) != str(row["project_id"]):
                    raise ValueError("SUPPORTED intervention evidence belongs to another project")
                if evidence_row["claim_status"] != "SUPPORTED":
                    raise ValueError("SUPPORTED intervention requires evidence attached to a supported claim")
            if any(s!="VERIFIED" for s in states): raise ValueError("SUPPORTED intervention requires all attached evidence to be VERIFIED")
            if row["evidence_level"] not in {"SUPPORTED","WELL_SUPPORTED"}: raise ValueError("SUPPORTED intervention requires supported evidence level")
        old=row["status"]; ts=now()
        with self.db.transaction() as con:
            updated=con.execute("UPDATE interventions SET status=? WHERE id=? AND status=?",(new_status,intervention_id,old))
            if updated.rowcount != 1: raise ValueError("intervention state changed concurrently")
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"intervention.status_changed","intervention",intervention_id,actor,json.dumps({"from":old,"to":new_status,"rationale":rationale}),ts))
        return self.db.one("SELECT * FROM interventions WHERE id=?",(intervention_id,))
