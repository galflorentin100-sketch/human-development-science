from app.database import Database
from app.workflow import ResearchCycle
from app.hds_company import HDSCompanyService

def test_company_analytics_is_descriptive_and_project_scoped(tmp_path):
    db=Database(str(tmp_path/"hds.db")); p=ResearchCycle(db).run("company")["project"]; other=ResearchCycle(db).run("other")["project"]; svc=HDSCompanyService(db)
    customer=svc.create_customer(p["id"],"c1"); product=svc.create_product(p["id"],"Program","SUBSCRIPTION","desc"); svc.subscribe(p["id"],customer["id"],product["id"])
    metrics=svc.analytics(p["id"]); assert metrics["customers"]==1; assert metrics["active_subscriber_customers"]==1; assert metrics["observed_conversion_rate"]==1.0; assert "causal" in metrics["data_policy"]
    assert svc.analytics(other["id"])["customers"]==0
