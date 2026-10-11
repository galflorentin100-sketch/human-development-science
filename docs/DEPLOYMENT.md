# Production deployment and owner bootstrap

This runbook is deliberately conservative: **do not expose the application directly to the public internet** until a trusted identity proxy is configured.

## Required architecture

- Python API container built from the repository Dockerfile.
- PostgreSQL database with persistent storage and tested encrypted backups.
- Production identity proxy / IdP that authenticates the founder and forwards a stable external subject.
- The trusted proxy must remove any client-supplied `X-External-Subject` and `X-External-Subject-Signature` headers, then set the authenticated subject and compute the HMAC-SHA256 signature of that exact subject using `HDS_AUTH_HMAC_SECRET`.
- The API must not be reachable around that proxy. The HMAC header is not a replacement for an authenticated proxy: a public client must never know the HMAC secret.
- Autonomous code execution must use the isolated worker configuration. Do not enable local code execution in production.

A generic public web-service deployment alone is not sufficient because it does not authenticate requests or sign identity headers.

## Required environment

Set these in the hosting provider's secret/environment settings; do not commit real values:

- `COMPANY_OS_ENV=production`
- `DATABASE_URL` — PostgreSQL URL.
- `HDS_AUTH_HMAC_SECRET` — long, randomly generated secret shared only by the API and trusted identity proxy.
- `HDS_OWNER_EXTERNAL_SUBJECT` — exact stable subject issued by the configured identity provider.
- `HDS_CODE_RUNNER_MODE=isolated`
- `COMPANY_OS_LOG_LEVEL=INFO`

Do not use SQLite for production. Do not enable a paid model provider until API credentials and explicit token-rate limits are configured.

## One-time founder provisioning

After setting the production environment and applying migrations, run this command once from a trusted administrative shell/container with access to the production database:

```bash
HDS_BOOTSTRAP_OWNER_EMAIL='your-email@example.com' python scripts/bootstrap_owner.py
```

The script refuses to run unless `COMPANY_OS_ENV=production`, checks that the owner subject is configured, and creates the configured subject as a founder. It is a command-line operation, not an HTTP endpoint. If an existing account is not a founder, it fails closed rather than silently escalating privileges.

Back up the database after provisioning and verify restore procedures before inviting any other user.

## First research from the phone

After deployment, verify:

1. `/health` responds.
2. `/ready` reports ready.
3. The identity proxy rejects unauthenticated requests and correctly signs the authenticated owner's subject.
4. The founder can load the dashboard and call authenticated API routes.
5. Create a research loop using `POST /api/hds/research-loops/bootstrap`.
6. Start it using `POST /api/hds/research-loops/{run_id}/start`.
7. Retrieve candidate literature using `POST /api/hds/research-loops/{run_id}/retrieve` with PubMed and Crossref.
8. Check `GET /api/hds/research-loops/{run_id}/sources`. Discovery results must remain unverified until the separate review workflow is completed.

Retrieval is discovery, not scientific verification. Do not report a research conclusion until source content has been reviewed and the synthesis has passed the required independent review and evidence gates.

## Current limitations

This runbook does not create hosting accounts, configure DNS/IdP policy, generate external secrets, or deploy infrastructure automatically. Those steps require access and explicit authorization in the hosting and identity-provider accounts. A working CI build is not evidence that a production deployment exists.
