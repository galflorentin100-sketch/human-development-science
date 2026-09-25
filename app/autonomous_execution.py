"""Bounded autonomous maintenance bridge. It creates work; it does not self-approve scientific changes."""
from app.autonomous_scientific_maintenance import AutonomousScientificMaintenance
class AutonomousExecutionBridge:
    def __init__(self,db): self.db=db
    def plan(self,project_id):
        return {"created_task_ids":AutonomousScientificMaintenance(self.db).create_tasks(project_id),
                "policy":"tasks still require normal execution, evaluation, permissions, approvals and scientific review"}
