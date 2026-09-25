"""Unified scientific system health snapshot."""
class ScientificSystemHealth:
    def __init__(self,db): self.db=db

    def snapshot(self):
        from app.self_audit import SelfAuditEngine
        from app.knowledge_freshness import KnowledgeFreshness
        from app.autonomous_scientific_maintenance import AutonomousScientificMaintenance
        audit=SelfAuditEngine(self.db).run()
        fresh=KnowledgeFreshness(self.db).scan()
        maintenance=AutonomousScientificMaintenance(self.db).propose()
        counts={}
        for table,key in [("claims","claims"),("evidence","evidence"),("research_findings","findings"),("interventions","interventions"),("training_protocols","training_protocols"),("studies","studies")]:
            try: counts[key]=self.db.one(f"SELECT COUNT(*) AS n FROM {table}")["n"]
            except Exception: counts[key]=None
        return {
            "status":"REVIEW_REQUIRED" if audit["findings"] or fresh["stale_count"] else "NOMINAL",
            "counts":counts,
            "audit_findings":len(audit["findings"]),
            "stale_knowledge":fresh["stale_count"],
            "maintenance_proposals":maintenance["count"],
            "policy":"health reports gaps; it never changes scientific state"
        }
