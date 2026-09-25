"""Read-only scientific control plane for founder/lab operations."""
class ScientificControlPlane:
    def __init__(self,db): self.db=db

    def snapshot(self):
        from app.self_audit import SelfAuditEngine
        from app.autonomous_scientific_maintenance import AutonomousScientificMaintenance
        from app.knowledge_freshness import KnowledgeFreshness
        from app.knowledge_impact import KnowledgeImpactAnalyzer
        from app.knowledge_graph import KnowledgeDependencyGraph
        audit=SelfAuditEngine(self.db).run()
        maintenance=AutonomousScientificMaintenance(self.db).propose()
        freshness=KnowledgeFreshness(self.db).scan()
        contradictions=KnowledgeImpactAnalyzer(self.db).contradiction_scan()
        graph=KnowledgeDependencyGraph(self.db).build()
        return {
            "policy":"read-only control plane; no scientific state mutation",
            "audit":audit,
            "maintenance":maintenance,
            "freshness":freshness,
            "contradictions":contradictions,
            "dependency_graph":graph,
            "gates":{
                "claims":sum(1 for x in graph["nodes"] if x["type"]=="CLAIM"),
                "interventions":sum(1 for x in graph["nodes"] if x["type"]=="INTERVENTION"),
                "training_protocols":sum(1 for x in graph["nodes"] if x["type"]=="TRAINING_PROTOCOL")
            }
        }
