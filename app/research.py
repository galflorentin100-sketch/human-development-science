from enum import Enum
class KnowledgeKind(str,Enum): FACT="FACT"; EVIDENCE="EVIDENCE"; HYPOTHESIS="HYPOTHESIS"; ASSUMPTION="ASSUMPTION"; UNKNOWN="UNKNOWN"
class ResearchRepository:
    def __init__(self,db): self.db=db
    def hypothesis(self,*args,**kwargs): return None
    def experiment(self,*args,**kwargs): return None
    def study(self,*args,**kwargs): return None
