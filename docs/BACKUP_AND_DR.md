# HDS Backup and Disaster Recovery

Production PostgreSQL backups must be stored outside the application host, encrypted at rest, access-controlled, and retained according to an operator-defined policy.

Create a backup:
```bash
DATABASE_URL='...' python scripts/backup_postgres.py --output-dir /secure/backups
```
The command creates a PostgreSQL custom-format dump plus SHA-256 sidecar and never prints the connection string.

Verify restoration only against a disposable PostgreSQL database:
```bash
DATABASE_URL='postgresql://.../hds_restore' python scripts/verify_postgres_backup.py /secure/backups/hds-postgres-<timestamp>.dump
```
The verifier checks the checksum, restores with `pg_restore`, and verifies the public schema.

Recovery sequence:
1. Provision a clean PostgreSQL instance.
2. Restore the latest verified backup.
3. Apply required forward migrations.
4. Run readiness and PostgreSQL smoke checks.
5. Validate Founder OS and critical HDS workflows.
6. Switch traffic only after application and data validation succeeds.

RPO/RTO are deployment-level targets and are not claimed by the repository until they are selected and exercised. A backup that has never been restored is not a verified recovery mechanism.
