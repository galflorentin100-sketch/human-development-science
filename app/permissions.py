from enum import Enum
class Permission(str,Enum):
    READ="READ"; WRITE="WRITE"; EXECUTE="EXECUTE"; PUBLISH="PUBLISH"; SPEND="SPEND"; DELETE="DELETE"; DEPLOY="DEPLOY"; CONTACT_EXTERNAL_PARTY="CONTACT_EXTERNAL_PARTY"
class PermissionDenied(Exception): pass
class PermissionService:
    def __init__(self,db): self.db=db
    def grant(self,agent_id,permission,granted_by="system"):
        self.db.execute("INSERT OR IGNORE INTO agent_permissions (agent_id,permission,granted_by,created_at) VALUES (?,?,?,datetime('now'))",(agent_id,permission.value if isinstance(permission,Permission) else permission,granted_by))
    def check(self,agent_id,permission,resource=""):
        p=permission.value if isinstance(permission,Permission) else permission
        row=self.db.one("SELECT 1 FROM agent_permissions WHERE agent_id=? AND permission=?",(agent_id,p))
        if not row: raise PermissionDenied(f"{agent_id} lacks {p} for {resource}")
