# Demo deployment preparation

Do not deploy this revision yet. The API has no authentication or ownership
checks, and its profile and task endpoints must not be exposed to users. The
web interface uses simulated speech and agent responses. It does not connect to
the backend or the Meta Model API. The phone flow also uses a demo agent.
The required Dockerfile and Railway service configuration are not supplied in
this revision. Resolve these gaps before asking the owner to approve a deploy.
Use no production Yosubi customer data.

## Environment variables

Set secrets in Railway's service variables, never in source files or logs.
The current code reads the following variables:

| Variable | Service | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | backend and scheduler | Required PostgreSQL connection URL. Use the managed database service reference. |
| `HOST` | backend | Bind address for `python -m app`. Defaults to `127.0.0.1`; set `0.0.0.0` explicitly only for the hosted container. |
| `PORT` | backend | Port for `python -m app`; defaults to `8000`. Use the port assigned by the hosting platform. |
| `TWILIO_AUTH_TOKEN` | backend and scheduler | Webhook signature verification; also needed for test calls. |
| `TWILIO_ACCOUNT_SID` | scheduler | Twilio test account identifier for test calls. |
| `TWILIO_FROM_NUMBER` | scheduler | Test call origin number. |
| `PHONE_TEST_DESTINATION` | scheduler | Single test call destination. |
| `PHONE_WEBHOOK_BASE_URL` | backend and scheduler | Exact externally configured webhook origin, without a trailing slash or path. |
| `PHONE_TEST_MODE` | scheduler | Set to `1` to enable test calls; otherwise delivery fails safely. |
| `PHONE_LANGUAGE` | scheduler | Set to `es` for Spanish calls; defaults to English. |
| `PYTHONPATH` | backend and scheduler | Set to `backend` when running from the repository root. |

`MODEL_API_KEY` is required by the target specification, but the current app
does not read it or make model calls. Do not claim model integration works by
setting it. The frontend currently reads no application environment variables.

## Owner-approved deployment sequence

1. Complete and review authentication and ownership checks, the container and
   service configuration, and the missing integrations. Confirm that health
   checks and a fresh demo database are configured. Do not use `create_all` to
   update an existing database; it only creates missing tables.
2. **Owner approval required:** approve the Railway project, managed Postgres,
   any charges, public domains, and the exact deployment revision.
3. After approval, create the Railway project and managed Postgres. Create the
   backend and frontend services from the approved revision. Configure each
   service's build, start command, and health check using the reviewed service
   configuration. A scheduler is a separate process and is not started by the
   API; provision one only if reminder execution is included in the approval.
4. **Owner approval required:** approve each environment variable and domain
   change. Set the applicable variables above in the appropriate Railway
   services. Reference the managed Postgres URL instead of copying credentials
   into the repository. Supply `MODEL_API_KEY` only when its integration exists.
5. **Owner approval required:** approve schema creation on the fresh demo
   database. Run `python -m app.database` in the backend service with
   `PYTHONPATH=backend` and `DATABASE_URL` set. Never run this against production
   Yosubi customer data.
6. **Owner approval required:** approve the deploy. Deploy the approved revision,
   then check the backend `/health` endpoint and the frontend over their approved
   URLs. A healthy endpoint does not prove database connectivity.
7. **Owner approval required:** approve any Twilio number, billing, webhook
   changes, and live calls separately. Configure the approved inbound webhook
   to `<backend-origin>/phone/inbound` and verify the signature setup. Test only
   with owner-approved test accounts, numbers, and data.

The exact service-specific build and start settings depend on the missing
container and Railway configuration; do not deploy until those are reviewed.
