"""Governed orchestration of HDS scientific work."""
from app.autonomous_research_cycle import AutonomousResearchCycle
from app.founder_intelligence import FounderIntelligence
from app.finding_generator import FindingGenerator

class ScientificOrchestrator:
    def __init__(self, db): self.db=db

    def cycle(self, project_id, protocol_ids=()):
        generated=[]
        for protocol_id in protocol_ids:
            generated.extend(FindingGenerator(self.db).from_training_outcomes(project_id,protocol_id))
        research=AutonomousResearchCycle(self.db).run(project_id)
        founder=FounderIntelligence(self.db).snapshot(project_id)
        return {
            "project_id":project_id,
            "generated_findings":generated,
            "research_cycle":research,
            "founder_snapshot":founder,
            "guardrail":"Automation proposes and summarizes; it does not silently promote scientific claims or bypass approval gates."
        }
