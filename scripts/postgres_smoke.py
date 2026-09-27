import os
import uuid

from app.database import PostgreSQLDatabase


def main():
    url = os.environ["DATABASE_URL"]
    db = PostgreSQLDatabase(url)
    db.migrate()

    company_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",
        (company_id, "ci", "ci", "ci", "truth", "2026-01-01T00:00:00+00:00"),
    )
    row = db.one("SELECT id,name FROM companies WHERE id=?", (company_id,))
    assert row and row["id"] == company_id

    # Migration regression: project-scoped columns must exist before their indexes.
    for table in ("claims","studies","experiments","research_workspaces","interventions","training_protocols"):
        assert "project_id" in db.table_columns(table), f"{table}.project_id missing after migration"
    index_names = {row["indexname"] for row in db.all("SELECT indexname FROM pg_indexes WHERE schemaname='public'")}
    for index_name in (
        "idx_claims_project_created",
        "idx_studies_project_created",
        "idx_experiments_project_created",
        "idx_research_workspaces_project_created",
        "idx_interventions_project_created",
        "idx_training_protocols_project_created",
    ):
        assert index_name in index_names, f"{index_name} missing after migration"

    # Exercise the conflict translation used by PostgreSQLDatabase._sql.
    db.execute(
        "INSERT OR IGNORE INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",
        (company_id, "ci", "ci", "ci", "truth", "2026-01-01T00:00:00+00:00"),
    )
    assert db.one("SELECT COUNT(*) AS n FROM companies WHERE id=?", (company_id,))["n"] == 1

    with db.transaction() as con:
        con.execute("UPDATE companies SET mission=%s WHERE id=%s", ("verified", company_id))
        assert con.execute("SELECT mission FROM companies WHERE id=%s", (company_id,)).fetchone()["mission"] == "verified"

    print("PostgreSQL smoke test passed")


if __name__ == "__main__":
    main()
