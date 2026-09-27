from app.database import Database
from app.workflow import ResearchCycle
from app.hds_company import HDSCompanyService


def test_hds_company_customer_product_enrollment_and_subscription_are_project_scoped(tmp_path):
    db=Database(str(tmp_path/"company.db"))
    first=ResearchCycle(db).run("company one")["project"]
    second=ResearchCycle(db).run("company two")["project"]
    svc=HDSCompanyService(db)

    customer=svc.create_customer(first["id"],"customer-1")
    product=svc.create_product(first["id"],"Resilience Program","PROGRAM","Structured human-development program")
    program_id=db.one("SELECT id FROM hds_programs WHERE project_id=?",(first["id"],))["id"]
    enrollment=svc.enroll_customer(program_id,customer["id"])
    subscription=svc.subscribe(first["id"],customer["id"],product["id"])

    assert enrollment["customer_id"]==customer["id"]
    assert subscription["product_id"]==product["id"]

    other_product=svc.create_product(second["id"],"Other","PROGRAM","Other project product")
    try:
        svc.subscribe(first["id"],customer["id"],other_product["id"])
        assert False
    except ValueError as exc:
        assert "project" in str(exc)


def test_hds_company_routes_are_wired():
    from app.main import app
    paths={route.path for route in app.routes}
    assert "/api/hds/company/customers" in paths
    assert "/api/hds/company/products" in paths
    assert "/api/hds/company/{project_id}" in paths
