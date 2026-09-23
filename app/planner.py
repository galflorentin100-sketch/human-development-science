class AutonomousPlanner:
    def __init__(self,db): self.db=db
    @staticmethod
    def priority(impact,urgency,confidence,feasibility,cost): return impact*urgency*confidence*feasibility/max(cost,0.01)
    def plan(self,project_id,candidates): return sorted(candidates,key=lambda x:self.priority(x.get("impact",1),x.get("urgency",1),x.get("confidence",1),x.get("feasibility",1),x.get("cost",1)),reverse=True)
