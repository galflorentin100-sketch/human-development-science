"""Dependency graph across scientific knowledge layers."""
class KnowledgeDependencyGraph:
    def __init__(self,db): self.db=db
    def build(self):
        nodes=[]; edges=[]
        for table,typ in [("claims","CLAIM"),("interventions","INTERVENTION"),("training_protocols","TRAINING_PROTOCOL")]:
            for r in self.db.all(f"SELECT * FROM {table}"):
                nodes.append({"id":r["id"],"type":typ,"status":r["status"]})
        for p in self.db.all("SELECT id,source_claim_id,intervention_id FROM training_protocols"):
            if p["source_claim_id"]: edges.append({"from":p["source_claim_id"],"to":p["id"],"relation":"GROUNDS"})
            if p["intervention_id"]: edges.append({"from":p["intervention_id"],"to":p["id"],"relation":"IMPLEMENTS"})
        return {"nodes":nodes,"edges":edges,"policy":"graph is descriptive; it does not infer efficacy"}
