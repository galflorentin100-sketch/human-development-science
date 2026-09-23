from __future__ import annotations
import json
from uuid import uuid4
from app.models import now
class CompanyState:
    def __init__(self,db): self.db=db
    def snapshot(self):
        return {"company":self.db.one("SELECT * FROM companies WHERE id='hds'"),"goals":self.db.all("SELECT * FROM goals WHERE status='ACTIVE'"),"active_projects":self.db.all("SELECT * FROM projects WHERE status IN ('RUNNING','PLANNED')"),"active_tasks":self.db.all("SELECT * FROM tasks WHERE status IN ('PLANNED','ASSIGNED','RUNNING','BLOCKED')"),"agents":self.db.all("SELECT id,name,role,status,version,manager FROM agents"),"risks":self.db.all("SELECT * FROM risks WHERE status='OPEN'"),"opportunities":self.db.all("SELECT * FROM opportunities WHERE status='OPEN'"),"experiments":self.db.all("SELECT * FROM experiments WHERE status!='COMPLETED'"),"decisions":self.db.all("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 10"),"failures":self.db.all("SELECT * FROM failures ORDER BY created_at DESC LIMIT 10"),"lessons":self.db.all("SELECT * FROM lessons ORDER BY created_at DESC LIMIT 10"),"approvals":self.db.all("SELECT * FROM approvals WHERE status='PENDING'")}
    def decision(self,decision,owner,alternatives,evidence,assumptions,confidence,expected_outcome,follow_up=None):
        i=str(uuid4()); self.db.execute("INSERT INTO decisions(id,company_id,decision,alternatives,evidence,assumptions,confidence,expected_outcome,actual_outcome,owner,follow_up,created_at) VALUES (?, 'hds', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",(i,decision,json.dumps(alternatives),json.dumps(evidence),json.dumps(assumptions),confidence,expected_outcome,owner,follow_up,now())); return self.db.one("SELECT * FROM decisions WHERE id=?",(i,))
    def failure(self,stage,expected,actual,root_cause,lesson,owner="system",contributing=None,corrective_action=None):
        i=str(uuid4()); self.db.execute("INSERT INTO failures(id,project_id,stage,expected_result,actual_result,root_cause,lesson,created_at,contributing_factors,corrective_action,owner) VALUES (?,NULL,?,?,?,?,?,?,?, ?,?)",(i,stage,expected,actual,root_cause,lesson,now(),json.dumps(contributing or []),corrective_action,owner)); self.db.execute("INSERT INTO lessons(id,company_id,lesson,source_failure_id,created_at) VALUES (?,?,?,?,?)",(str(uuid4()),"hds",lesson,i,now())); return self.db.one("SELECT * FROM failures WHERE id=?",(i,))
