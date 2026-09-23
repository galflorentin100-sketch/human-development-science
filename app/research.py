from __future__ import annotations
import json
from uuid import uuid4
from app.models import now
class ResearchRepository:
    def __init__(self,db): self.db=db
    def hypothesis(self,project_id,statement,status="OPEN"):
        i=str(uuid4()); self.db.execute("INSERT INTO hypotheses(id,project_id,statement,status,created_at) VALUES (?,?,?,?,?)",(i,project_id,statement,status,now())); return self.db.one("SELECT * FROM hypotheses WHERE id=?",(i,))
    def experiment(self,project_id,hypothesis,design,status="PLANNED"):
        i=str(uuid4()); self.db.execute("INSERT INTO experiments(id,project_id,hypothesis,status,design,created_at) VALUES (?,?,?,?,?,?)",(i,project_id,hypothesis,status,design,now())); return self.db.one("SELECT * FROM experiments WHERE id=?",(i,))
    def result(self,experiment_id,outcome,interpretation):
        i=str(uuid4()); self.db.execute("INSERT INTO experiment_results(id,experiment_id,outcome,interpretation,created_at) VALUES (?,?,?,?,?)",(i,experiment_id,outcome,interpretation,now())); self.db.execute("UPDATE experiments SET result=?,status='COMPLETED' WHERE id=?",(interpretation,experiment_id)); return self.db.one("SELECT * FROM experiment_results WHERE id=?",(i,))
    def study(self,source_id,title,design,population,findings):
        i=str(uuid4()); self.db.execute("INSERT INTO studies(id,source_id,title,design,population,findings,created_at) VALUES (?,?,?,?,?,?,?)",(i,source_id,title,design,population,findings,now())); return self.db.one("SELECT * FROM studies WHERE id=?",(i,))
    def knowledge(self,project_id,kind,content,provenance):
        i=str(uuid4()); self.db.execute("INSERT INTO knowledge_items(id,project_id,kind,content,provenance,created_at) VALUES (?,?,?,?,?,?)",(i,project_id,kind,content,provenance,now())); return self.db.one("SELECT * FROM knowledge_items WHERE id=?",(i,))
