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
