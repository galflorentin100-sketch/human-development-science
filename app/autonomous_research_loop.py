"""Governed autonomous research-loop coordinator.

This service only advances workflow state. It never bypasses evidence review or
claim governance, and every transition is project-scoped.
"""
from uuid import uuid4
from app.models import now
from app.research_engine import ResearchEngine

class AutonomousResearchLoop:
    def __init__(self,db): self.db=db
    def create_gap(self,project_id,gap,owner="system"):
        if not self.db.one("SELECT id FROM projects WHERE id=?",(project_id,)): raise ValueError("project not found")
        if not str(gap or "").strip(): raise ValueError("knowledge gap is required")
        i=str(uuid4()); ts=now()
        self.db.execute("INSERT INTO research_loop_runs(id,project_id,gap,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",(i,project_id,gap.strip(),"GAP_IDENTIFIED",ts,ts))
        return self.get(i)
    def start_research(self,run_id,owner="system"):
        run=self.get(run_id)
        claimed=self.db.execute(
            "UPDATE research_loop_runs SET status='RESEARCH_STARTING',updated_at=? WHERE id=? AND status='GAP_IDENTIFIED'",
            (now(),run_id),
        ).rowcount
        if claimed != 1:
            raise ValueError("research can only start from GAP_IDENTIFIED")
        try:
            ws=ResearchEngine(self.db).create(run["project_id"],run["gap"],scope="HDS knowledge gap",owner=owner)
            ResearchEngine(self.db).activate(ws["id"],owner)
            self.db.execute(
                "UPDATE research_loop_runs SET workspace_id=?,status='RESEARCH_ACTIVE',updated_at=? WHERE id=? AND status='RESEARCH_STARTING'",
                (ws["id"],now(),run_id),
            )
            return self.get(run_id)
        except Exception:
            self.db.execute(
                "UPDATE research_loop_runs SET status='GAP_IDENTIFIED',updated_at=? WHERE id=? AND status='RESEARCH_STARTING'",
                (now(),run_id),
            )
            raise
    def attach_synthesis(self,run_id,synthesis_id):
        run=self.get(run_id); syn=self.db.one("SELECT rs.*,rw.project_id FROM research_syntheses rs JOIN research_workspaces rw ON rw.id=rs.workspace_id WHERE rs.id=?",(synthesis_id,))
        if not syn or syn["project_id"]!=run["project_id"] or syn["workspace_id"]!=run["workspace_id"]: raise ValueError("synthesis is outside this research loop")
        if syn["status"]!="ACCEPTED": raise ValueError("research synthesis must be independently reviewed and ACCEPTED")
        from app.research_engine import ResearchEngine
        readiness=ResearchEngine(self.db).readiness(synthesis_id)
        if not readiness["ready"]: raise ValueError("research synthesis is not ready: "+",".join(readiness["blockers"]))
        if run["status"]!="RESEARCH_ACTIVE": raise ValueError("loop is not awaiting synthesis")
        self.db.execute("UPDATE research_loop_runs SET synthesis_id=?,status='SYNTHESIS_READY',updated_at=? WHERE id=? AND status='RESEARCH_ACTIVE'",(synthesis_id,now(),run_id))
        return self.get(run_id)
    def promote_reviewed_synthesis_to_finding(self,run_id,actor="system"):
        run=self.get(run_id)
        if run["status"]!="SYNTHESIS_READY": raise ValueError("loop is not awaiting finding")
        from app.research_engine import ResearchEngine
        finding=ResearchEngine(self.db).promote_to_candidate_finding(run["synthesis_id"],actor)
        return self.attach_finding(run_id,finding["id"])

    def attach_finding(self,run_id,finding_id):
        run=self.get(run_id); f=self.db.one("SELECT * FROM research_findings WHERE id=?",(finding_id,))
        if not f or f["project_id"]!=run["project_id"]: raise ValueError("finding is outside this project")
        if f["source_id"]!=run["synthesis_id"]: raise ValueError("finding is not derived from this loop synthesis")
        if run["status"]!="SYNTHESIS_READY": raise ValueError("loop is not awaiting finding")
        self.db.execute("UPDATE research_loop_runs SET finding_id=?,status='FINDING_CANDIDATE',updated_at=? WHERE id=? AND status='SYNTHESIS_READY'",(finding_id,now(),run_id))
        return self.get(run_id)
    def mark_claimed(self,run_id,claim_id):
        run=self.get(run_id); claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim or claim["project_id"]!=run["project_id"]: raise ValueError("claim is outside this project")
        if run["status"]!="FINDING_CANDIDATE": raise ValueError("loop is not awaiting claim")
        # Claim provenance must explicitly point to the finding.
        rev=self.db.one("SELECT id FROM claim_revisions WHERE claim_id=? AND source_finding_id=? ORDER BY created_at DESC LIMIT 1",(claim_id,run["finding_id"]))
        if not rev: raise ValueError("claim must have explicit finding provenance")
        self.db.execute("UPDATE research_loop_runs SET claim_id=?,status='CLAIM_CANDIDATE',updated_at=? WHERE id=? AND status='FINDING_CANDIDATE'",(claim_id,now(),run_id))
        return self.get(run_id)
    def ready_for_intervention(self,run_id):
        run=self.get(run_id)
        if run["status"]!="CLAIM_CANDIDATE": return {"ready":False,"reason":"claim is not linked"}
        claim=self.db.one("SELECT status,classification,confidence FROM claims WHERE id=?",(run["claim_id"],))
        if not claim: return {"ready":False,"reason":"claim missing"}
        if claim["status"]!="SUPPORTED": return {"ready":False,"reason":"claim is not SUPPORTED"}
        if claim["classification"] not in {"FACT","INFERENCE"}: return {"ready":False,"reason":"claim classification is not intervention-eligible"}
        return {"ready":True,"claim":claim,"policy":"eligibility gate only; does not imply efficacy"}
    def next_action(self,run_id):
        run=self.get(run_id)
        actions={
            "GAP_IDENTIFIED":"START_RESEARCH",
            "RESEARCH_ACTIVE":"COMPLETE_RESEARCH_AND_SUBMIT_REVIEWED_SYNTHESIS",
            "SYNTHESIS_READY":"PROMOTE_TO_CANDIDATE_FINDING",
            "FINDING_CANDIDATE":"CREATE_CLAIM_WITH_FINDING_PROVENANCE",
            "CLAIM_CANDIDATE":"SCIENTIFIC_ADMISSION_RECHECK",
        }
        action=actions.get(run["status"],"OBSERVE")
        return {"run":run,"next_action":action,"terminal":run["status"] in {"INTERVENTION_READY","CLOSED","FAILED"}}
    def get(self,run_id):
        row=self.db.one("SELECT * FROM research_loop_runs WHERE id=?",(run_id,))
        if not row: raise ValueError("research loop not found")
        return row
