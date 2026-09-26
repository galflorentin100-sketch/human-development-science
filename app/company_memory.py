"""Auditable company memory for decisions, findings, failures and system lessons."""
from uuid import uuid4
from app.models import now

class CompanyMemory:
    def __init__(self,db):
        self.db=db
        self.db.execute("CREATE TABLE IF NOT EXISTS company_memory (id TEXT PRIMARY KEY, project_id TEXT, memory_type TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, source_type TEXT, source_id TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL)")

    def record(self,project_id,memory_type,title,content,created_by,source_type=None,source_id=None):
        if not str(title or "").strip() or not str(content or "").strip(): raise ValueError("memory title and content are required")
        i=str(uuid4())
        self.db.execute("INSERT INTO company_memory(id,project_id,memory_type,title,content,source_type,source_id,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(i,project_id,memory_type,title,content,source_type,source_id,created_by,now()))
        return self.get(i)

    def get(self,memory_id):
        row=self.db.one("SELECT * FROM company_memory WHERE id=?",(memory_id,))
        if not row: raise ValueError("memory not found")
        return row

    def search(self,project_id,query="",memory_type=None,limit=50):
        q="SELECT * FROM company_memory WHERE project_id=?"; p=[project_id]
        if memory_type: q+=" AND memory_type=?"; p.append(memory_type)
        if query:
            q+=" AND (title LIKE ? OR content LIKE ?)"; like="%"+query+"%"; p.extend([like,like])
        q+=" ORDER BY created_at DESC LIMIT ?"; p.append(int(limit))
        return self.db.all(q,tuple(p))
