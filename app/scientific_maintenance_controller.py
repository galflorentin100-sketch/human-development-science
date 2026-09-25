"""Bounded autonomous scientific maintenance.

The system may discover and queue work automatically, but execution that changes
scientific state remains approval-gated and auditable.
"""
import json
from uuid import uuid4
from app.models import now

class ScientificMaintenanceController:
    def __init__(self,db): self.db=db

    def discover(self):
        from app.autonomous_scientific_maintenance import AutonomousScientificMaintenance
        proposals=AutonomousScientificMaintenance(self.db).propose()["proposals"]
        created=[]
        for p in proposals:
            existing=self.db.one("SELECT * FROM maintenance_work WHERE kind=? AND entity_type=? AND entity_id=? AND status IN ('PROPOSED','APPROVAL_PENDING','APPROVED','IN_PROGRESS')",
                                 (p["kind"],p["entity_type"],p["entity_id"]))
            if existing:
                created.append(existing); continue
            i=str(uuid4())
            self.db.execute("""INSERT INTO maintenance_work
                (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (i,p["kind"],p["entity_type"],p["entity_id"],p["title"],p["reason"],p["success_criteria"],"PROPOSED",None,now(),now()))
            created.append(self.db.one("SELECT * FROM maintenance_work WHERE id=?",(i,)))
        return {"created_or_existing":created,"count":len(created)}

    def request_approval(self,work_id,actor):
        work=self.db.one("SELECT * FROM maintenance_work WHERE id=?",(work_id,))
        if not work: raise ValueError("maintenance work not found")
        if work["status"]!="PROPOSED": raise ValueError("maintenance work is not awaiting approval")
        from app.approvals import ApprovalService
        approval=ApprovalService(self.db).request(
            action="EXECUTE_SCIENTIFIC_MAINTENANCE",
            requested_by=actor,
            reason=work["reason"],
            risk_level="MEDIUM",
            context={"maintenance_work_id":work_id,"entity_type":work["entity_type"],"entity_id":work["entity_id"],"success_criteria":work["success_criteria"]})
        self.db.execute("UPDATE maintenance_work SET status='APPROVAL_PENDING',approval_id=?,updated_at=? WHERE id=?",(approval["id"],now(),work_id))
        return self.db.one("SELECT * FROM maintenance_work WHERE id=?",(work_id,))

    def approve(self,work_id,actor):
        work=self.db.one("SELECT * FROM maintenance_work WHERE id=?",(work_id,))
        if not work or work["status"]!="APPROVAL_PENDING": raise ValueError("maintenance work is not approval-pending")
        from app.approvals import ApprovalService
        approval=ApprovalService(self.db).resolve(work["approval_id"],"APPROVED",actor)
        self.db.execute("UPDATE maintenance_work SET status='APPROVED',updated_at=? WHERE id=?",(now(),work_id))
        return {"work":self.db.one("SELECT * FROM maintenance_work WHERE id=?",(work_id,)),"approval":approval}

    def dispatch(self,work_id,actor):
        work=self.db.one("SELECT * FROM maintenance_work WHERE id=?",(work_id,))
        if not work: raise ValueError("maintenance work not found")
        from app.approvals import ApprovalService
        if work["status"]!="APPROVED": raise ValueError("maintenance work requires approval")
        ApprovalService(self.db).require(work["approval_id"])
        self.db.execute("UPDATE maintenance_work SET status='IN_PROGRESS',updated_at=? WHERE id=? AND status='APPROVED'",(now(),work_id))
        return {"status":"DISPATCHED","work":self.db.one("SELECT * FROM maintenance_work WHERE id=?",(work_id,)),"policy":"dispatch creates/assigns research work; it does not mutate scientific truth"}
