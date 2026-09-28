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
    def __init__(self,db,owner_external_subject=None):
        self.db=db
        self.owner_external_subject=owner_external_subject
        self._seed_roles()

    def _require_owner(self,external_subject):
        if self.owner_external_subject is not None and external_subject != self.owner_external_subject:
            raise PermissionError("principal is not the configured system owner")
    def _seed_roles(self):
        roles=[("founder",["READ","WRITE","EXECUTE","PUBLISH","SPEND","DELETE","DEPLOY","CONTACT_EXTERNAL_PARTY","APPROVE"]),("operator",["READ","WRITE","EXECUTE"]),("reviewer",["READ","WRITE"])]
        for name,permissions in roles:
            row=self.db.one("SELECT id FROM roles WHERE name=?",(name,))
            if not row:
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
    def grant_project_access(self, actor_external_subject, target_external_subject, project_id, role="operator"):
        if role not in {"founder","operator","reviewer"}:
            raise ValueError("unknown role")
        actor=self.authorize(actor_external_subject)
        if actor.role != "founder":
            raise PermissionError("only founder can grant project access")
        user=self.db.one("SELECT * FROM users WHERE external_subject=?",(target_external_subject,))
        if not user: raise PermissionError("unknown principal")
        project=self.db.one("SELECT id FROM projects WHERE id=? AND company_id='hds'",(project_id,))
        if not project: raise ValueError("project not found")
        role_row=self.db.one("SELECT id FROM roles WHERE name=?",(role,))
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO project_memberships(project_id,user_id,role_id,status,created_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(project_id,user_id) DO UPDATE SET role_id=excluded.role_id,status='ACTIVE'",
                (project_id,user["id"],role_row["id"],"ACTIVE",now()))
        return self.project_authorize(target_external_subject,project_id)

    def project_authorize(self, external_subject, project_id, required_permission=None):
        user=self.db.one("SELECT * FROM users WHERE id=? OR external_subject=? LIMIT 1",(external_subject,external_subject))
        if not user: raise PermissionError("unknown principal")
        company=self.db.one(
            "SELECT r.permissions FROM company_memberships m JOIN roles r ON r.id=m.role_id "
            "WHERE m.company_id='hds' AND m.user_id=? AND m.status='ACTIVE'",(user["id"],))
        if not company: raise PermissionError("inactive membership")
        membership=self.db.one(
            "SELECT r.name,r.permissions FROM project_memberships pm "
            "JOIN roles r ON r.id=pm.role_id "
            "JOIN projects p ON p.id=pm.project_id "
            "WHERE pm.project_id=? AND pm.user_id=? AND pm.status='ACTIVE' AND p.company_id='hds'",
            (project_id,user["id"]))
        if not membership:
            raise PermissionError("project access denied")
        permissions=set(json.loads(membership["permissions"]))
        if required_permission and required_permission not in permissions:
            raise PermissionError("permission denied")
        return Principal(user["id"],membership["name"],permissions)

    def authorize(self,external_subject,required_permission=None):
        self._require_owner(external_subject)
        user=self.db.one("SELECT * FROM users WHERE external_subject=?",(external_subject,))
        if not user: raise PermissionError("unknown principal")
        membership=self.db.one("SELECT r.permissions FROM company_memberships m JOIN roles r ON r.id=m.role_id WHERE m.company_id='hds' AND m.user_id=? AND m.status='ACTIVE'",(user["id"],))
        if not membership: raise PermissionError("inactive membership")
        if required_permission and required_permission not in json.loads(membership["permissions"]): raise PermissionError("permission denied")
        role=self.db.one("SELECT r.name FROM company_memberships m JOIN roles r ON r.id=m.role_id WHERE m.company_id='hds' AND m.user_id=?",(user["id"],))["name"]
        return Principal(user["id"],role,json.loads(membership["permissions"]))
