"""One-time, local/console-only provisioning for the configured production owner.

Run from a trusted administrative shell with DATABASE_URL and the production
identity settings configured. Never expose this script as an HTTP endpoint.
"""
import os

from app.auth import AuthService
from app.config import Settings
from app.database import database_from_settings


def provision_owner(db, external_subject: str, email: str, configured_owner: str):
    subject = str(external_subject or "").strip()
    owner = str(configured_owner or "").strip()
    normalized_email = str(email or "").strip()
    if not subject or not owner or subject != owner:
        raise ValueError("external subject must exactly match HDS_OWNER_EXTERNAL_SUBJECT")
    if not normalized_email or "@" not in normalized_email:
        raise ValueError("a valid HDS_BOOTSTRAP_OWNER_EMAIL is required")

    service = AuthService(db, owner)
    user = service.create_user(subject, normalized_email, role="founder")
    membership = db.one(
        """SELECT r.name FROM company_memberships m
           JOIN roles r ON r.id=m.role_id
           WHERE m.company_id='hds' AND m.user_id=? AND m.status='ACTIVE'""",
        (user["id"],),
    )
    if not membership or membership["name"] != "founder":
        raise RuntimeError(
            "configured owner already exists without active founder membership; "
            "resolve this explicitly rather than silently escalating privileges"
        )
    return {"user_id": user["id"], "external_subject": subject, "role": membership["name"]}


def main():
    settings = Settings.load()
    if settings.environment != "production":
        raise SystemExit("Refusing owner provisioning unless COMPANY_OS_ENV=production")
    email = os.getenv("HDS_BOOTSTRAP_OWNER_EMAIL", "")
    db = database_from_settings(settings)
    db.migrate()
    result = provision_owner(
        db,
        settings.owner_external_subject or "",
        email,
        settings.owner_external_subject or "",
    )
    print(f"Provisioned HDS owner: role={result['role']} user_id={result['user_id']}")


if __name__ == "__main__":
    main()
