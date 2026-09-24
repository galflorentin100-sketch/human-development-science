from enum import Enum
class Permission(str,Enum):
    READ="READ"; WRITE="WRITE"; EXECUTE="EXECUTE"; PUBLISH="PUBLISH"; SPEND="SPEND"; DELETE="DELETE"; DEPLOY="DEPLOY"; CONTACT_EXTERNAL_PARTY="CONTACT_EXTERNAL_PARTY"; APPROVE="APPROVE"
class PermissionDenied(Exception): pass
class PermissionService:
    def __init__(self,db): self.db=db
    def grant(self,agent_id,permission,granted_by="system"):
        p=permission.value if isinstance(permission,Permission) else permission
        self.db.execute("INSERT OR IGNORE INTO agent_permissions(agent_id,permission) VALUES (?,?)",(agent_id,p))
    def check(self,agent_id,permission,resource=""):
        p=permission.value if isinstance(permission,Permission) else permission
        if not self.db.one("SELECT 1 FROM agent_permissions WHERE agent_id=? AND permission=?",(agent_id,p)):
            raise PermissionDenied(f"{agent_id} lacks {p} for {resource}")
