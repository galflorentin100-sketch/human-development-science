from uuid import uuid4
import json
from app.models import now
class Principal:
    def __init__(self,user_id,role="founder",permissions=None):
        self.user_id=user_id
        self.role=role
        self.permissions=set(permissions or [])
    def can(self,permission):
        return permission in self.permissions
class AuthService:
    def __init__(self,db): self.db=db; self._seed_roles()
    def _seed_roles(self):
        roles=[("founder",["READ","WRITE","EXECUTE","PUBLISH","SPEND","DELETE","DEPLOY","CONTACT_EXTERNAL_PARTY","APPROVE"]),("operator",["READ","WRITE","EXECUTE"]),("reviewer",["READ","WRITE"])]
        for name,permissions in roles:
            row=self.db.one("SELECT id FROM roles WHERE name=?",(name,))
            if row:
                self.db.execute("UPDATE roles SET permissions=? WHERE id=?",(json.dumps(permissions),row["id"]))
            else:
                self.db.execute("INSERT INTO roles(id,name,permissions) VALUES (?,?,?)",(str(uuid4()),name,json.dumps(permissions)))

    def create_user(self,external_subject,email,role="operator"):
        if role not in {"founder","operator","reviewer"}: raise ValueError("unknown role")
        role_row=self.db.one("SELECT id FROM roles WHERE name=?",(role,))
        existing=self.db.one("SELECT * FROM users WHERE external_subject=?",(external_subject,))
        if existing:
            if existing["email"] != email: raise ValueError("external subject already exists with a different email")
            return existing
        uid=str(uuid4())
        with self.db.transaction() as con:
            con.execute("INSERT INTO users(id,external_subject,email,created_at) VALUES (?,?,?,?)",(uid,external_subject,email,now()))
            con.execute("INSERT INTO company_memberships(company_id,user_id,role_id,status,created_at) VALUES ('hds',?,?,'ACTIVE',?)",(uid,role_row["id"],now()))
        return self.db.one("SELECT * FROM users WHERE id=?",(uid,))
    def authorize(self,external_subject,required_permission=None):
        user=self.db.one("SELECT * FROM users WHERE external_subject=?",(external_subject,))
        if not user: raise PermissionError("unknown principal")
        membership=self.db.one("SELECT r.permissions FROM company_memberships m JOIN roles r ON r.id=m.role_id WHERE m.company_id='hds' AND m.user_id=? AND m.status='ACTIVE'",(user["id"],))
        if not membership: raise PermissionError("inactive membership")
        if required_permission and required_permission not in json.loads(membership["permissions"]): raise PermissionError("permission denied")
        role=self.db.one("SELECT r.name FROM company_memberships m JOIN roles r ON r.id=m.role_id WHERE m.company_id='hds' AND m.user_id=?",(user["id"],))["name"]
        return Principal(user["id"],role,json.loads(membership["permissions"]))
