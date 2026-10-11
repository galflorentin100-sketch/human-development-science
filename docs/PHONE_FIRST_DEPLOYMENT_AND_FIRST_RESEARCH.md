# Phone-first deployment and first scientific research runbook

## Current release status

This runbook is intentionally conservative. Passing CI proves that the checked-in tests, PostgreSQL smoke test, and container builds passed; it does **not** prove that the app is deployed, that an external identity proxy is configured, or that a live literature search has completed.

Deploy the `completion/hds-v1` branch only after reviewing its integration PR. Do not merge the integration PR without explicit owner approval.

## Non-negotiable production security

The API accepts a trusted identity through `X-External-Subject` and, in production, verifies `X-External-Subject-Signature` as an HMAC-SHA256 signature of that exact subject using `HDS_AUTH_HMAC_SECRET`.

- Do not expose the API directly to the public internet without a trusted authentication gateway that validates the user and injects a signature HDS can verify.
- Never let a browser/mobile client create its own trusted identity headers or learn the HMAC secret.
- Do not deploy with `COMPANY_OS_ENV=development`; development mode grants broad local permissions without production authentication.
- Use PostgreSQL in production, not the local SQLite database.
- Configure `HDS_OWNER_EXTERNAL_SUBJECT` to exactly match the stable subject emitted by the trusted identity gateway.
- Store database credentials and HMAC secret only in the hosting provider's secret manager. Never commit real credentials to Git.
- Keep model execution on the safe local provider until external model use, spend limits, and a valid model key have been deliberately configured.
- Configure HTTPS, backups, restore verification, health monitoring, and a restricted admin path before real use.

A hosting provider alone does not satisfy these requirements. If the chosen platform cannot provide a trusted identity gateway that signs the subject, deployment is blocked until a compatible gateway is configured.

## Required production configuration

Set these as managed environment variables/secrets in the hosting platform:

- `COMPANY_OS_ENV=production`
- `DATABASE_URL` — PostgreSQL connection string
- `HDS_AUTH_HMAC_SECRET` — long random secret, not checked into source control
- `HDS_OWNER_EXTERNAL_SUBJECT` — stable owner identity issued by the trusted gateway
- `HDS_MODEL_PROVIDER=local` unless paid model use has been explicitly approved
- `HDS_INPUT_COST_PER_MILLION_TOKENS` and `HDS_OUTPUT_COST_PER_MILLION_TOKENS` only if external model spend is intentionally enabled

The production container should run the application server from the repository's production Docker configuration. Follow the current `docker-compose.production.yml` and deployment scripts; do not substitute a development command for production.

## First-run verification

1. Confirm the deployment is HTTPS-only and the gateway requires sign-in.
2. Confirm unauthenticated requests to `/api/intelligence` return HTTP 401.
3. Confirm a valid signed owner request succeeds and an invalid signature returns HTTP 401.
4. Confirm `/health` returns healthy without leaking secrets or database credentials.
5. From the authenticated owner session, create a research loop with:
   `POST /api/hds/research-loops/bootstrap`
   JSON body:
   `{"question":"What is self-discipline, what components does it include, and what interventions develop it? Distinguish established findings, uncertainty, and hypotheses; prioritize systematic reviews and meta-analyses, then primary studies."}`
6. Start the returned run:
   `POST /api/hds/research-loops/{run_id}/start`
7. Retrieve a bounded set of sources:
   `POST /api/hds/research-loops/{run_id}/retrieve`
   JSON body:
   `{"providers":["pubmed","crossref"],"limit":20}`
8. Inspect the returned records and `GET /api/hds/research-loops/{run_id}/sources`. Retrieval status is **discovery only**: records and abstracts are unverified source material, not validated evidence.
9. Verify each source's title, DOI/PMID, publication details, and abstract against the publisher/index record before attaching evidence or promoting any claim.
10. Keep unsupported or conflicting claims uncertain. Do not present a synthesis as established fact until the independent review and provenance gates pass.

## Definition of done for the first research

The first research is complete only when:
- the app is reachable on the owner's phone over HTTPS;
- owner authentication and project-scoped authorization are verified;
- live PubMed and/or Crossref requests have actually returned records;
- source metadata and available abstracts are persisted and traceable to the retrieval run;
- independent review and evidence provenance are recorded;
- the final report separates FACT, INFERENCE, HYPOTHESIS, and OPINION and documents search scope, exclusions, limitations, and unresolved contradictions.

A green CI run alone does not meet this definition.
