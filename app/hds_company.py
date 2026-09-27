"""Business operations for the HDS human-development company layer."""
from uuid import uuid4
from app.models import now

class HDSCompanyService:
    def __init__(self, db):
        self.db=db

    def _project(self, project_id):
        if not self.db.one("SELECT id FROM projects WHERE id=?", (project_id,)):
            raise ValueError("project not found")

    def create_customer(self, project_id, external_ref, customer_type="INDIVIDUAL"):
        self._project(project_id)
        if not str(external_ref or "").strip(): raise ValueError("customer reference is required")
        i=str(uuid4())
        try:
            self.db.execute("""INSERT INTO hds_customers
                (id,project_id,external_ref,customer_type,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?)""",
                (i,project_id,external_ref.strip(),customer_type.strip(),"ACTIVE",now(),now()))
        except Exception as exc:
            raise ValueError("customer already exists in this project") from exc
        return self.db.one("SELECT * FROM hds_customers WHERE id=?", (i,))

    def create_organization(self, project_id, name, organization_type="ORGANIZATION"):
        self._project(project_id)
        if not str(name or "").strip(): raise ValueError("organization name is required")
        i=str(uuid4())
        self.db.execute("""INSERT INTO hds_organizations
            (id,project_id,name,organization_type,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)""",
            (i,project_id,name.strip(),organization_type.strip(),"ACTIVE",now(),now()))
        return self.db.one("SELECT * FROM hds_organizations WHERE id=?", (i,))

    def create_product(self, project_id, name, product_type, description):
        self._project(project_id)
        if not all(str(x or "").strip() for x in (name,product_type,description)):
            raise ValueError("product fields are required")
        i=str(uuid4())
        self.db.execute("""INSERT INTO hds_products
            (id,project_id,name,product_type,description,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (i,project_id,name.strip(),product_type.strip(),description.strip(),"ACTIVE",now(),now()))
        return self.db.one("SELECT * FROM hds_products WHERE id=?", (i,))

    def enroll_customer(self, program_id, customer_id):
        row=self.db.one("""SELECT p.project_id AS program_project,c.project_id AS customer_project
            FROM hds_programs p JOIN hds_customers c ON c.id=? WHERE p.id=?""",
            (customer_id,program_id))
        if not row: raise ValueError("program or customer not found")
        if row["program_project"] != row["customer_project"]:
            raise ValueError("customer and program belong to different projects")
        i=str(uuid4())
        self.db.execute("""INSERT INTO hds_program_enrollments
            (id,program_id,customer_id,status,started_at,ended_at)
            VALUES (?,?,?,?,?,?)""",
            (i,program_id,customer_id,"ACTIVE",now(),None))
        return self.db.one("SELECT * FROM hds_program_enrollments WHERE id=?", (i,))

    def create_coach(self, project_id, external_ref, role="COACH"):
        self._project(project_id)
        if not str(external_ref or "").strip(): raise ValueError("coach reference is required")
        i=str(uuid4())
        try:
            self.db.execute("""INSERT INTO hds_coaches
                (id,project_id,external_ref,role,status,created_at)
                VALUES (?,?,?,?,?,?)""",
                (i,project_id,external_ref.strip(),role.strip(),"ACTIVE",now()))
        except Exception as exc:
            raise ValueError("coach already exists in this project") from exc
        return self.db.one("SELECT * FROM hds_coaches WHERE id=?", (i,))

    def subscribe(self, project_id, customer_id, product_id):
        self._project(project_id)
        row=self.db.one("""SELECT c.project_id AS customer_project,p.project_id AS product_project
            FROM hds_customers c JOIN hds_products p ON p.id=? WHERE c.id=?""",
            (product_id,customer_id))
        if not row: raise ValueError("customer or product not found")
        if row["customer_project"] != project_id or row["product_project"] != project_id:
            raise ValueError("customer and product must belong to the project")
        i=str(uuid4())
        self.db.execute("""INSERT INTO hds_subscriptions
            (id,project_id,customer_id,product_id,status,started_at,ended_at)
            VALUES (?,?,?,?,?,?,?)""",
            (i,project_id,customer_id,product_id,"ACTIVE",now(),None))
        return self.db.one("SELECT * FROM hds_subscriptions WHERE id=?", (i,))

    def snapshot(self, project_id):
        self._project(project_id)
        return {
            "customers":self.db.all("SELECT * FROM hds_customers WHERE project_id=? ORDER BY created_at DESC",(project_id,)),
            "organizations":self.db.all("SELECT * FROM hds_organizations WHERE project_id=? ORDER BY created_at DESC",(project_id,)),
            "products":self.db.all("SELECT * FROM hds_products WHERE project_id=? ORDER BY created_at DESC",(project_id,)),
            "coaches":self.db.all("SELECT * FROM hds_coaches WHERE project_id=? ORDER BY created_at DESC",(project_id,)),
            "subscriptions":self.db.all("SELECT * FROM hds_subscriptions WHERE project_id=? ORDER BY started_at DESC",(project_id,)),
            "active_enrollments":self.db.all("""SELECT e.*,c.external_ref AS customer_ref,p.name AS program_name
                FROM hds_program_enrollments e JOIN hds_customers c ON c.id=e.customer_id
                JOIN hds_programs p ON p.id=e.program_id
                WHERE c.project_id=? AND e.status='ACTIVE' ORDER BY e.started_at DESC""",(project_id,))
        }
