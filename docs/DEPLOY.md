# Demo deployment runbook (Railway)

Target: public demo for hackathon judging (Nov 4-8). Three services plus
managed Postgres, all from this repo's `dev` branch at the approved commit.

Services:

- `backend`: Dockerfile at repo root. Start `python -m app`.
  Health check `/health`. Needs `HOST=0.0.0.0`, `PORT` from platform.
- `frontend`: `frontend/` directory, Nixpacks builder.
  Start `npx next start --hostname 0.0.0.0 -p $PORT`. Health check `/`.
  `NEXT_PUBLIC_DEMO_API_TOKEN` is baked at build time.
- `scheduler`: Dockerfile at repo root. Start `python -m app.scheduler`.
  No health check; it loops `run_due` every second.
- `postgres`: Railway managed plugin. Reference its `DATABASE_URL`.

Environment variables (set in Railway service variables, never in files):

| Variable | Services | Notes |
| --- | --- | --- |
| `DATABASE_URL` | backend, scheduler | Managed Postgres reference. |
| `MODEL_API_KEY` | backend | Meta Model API key. Server-side only. |
| `MODEL_ID` | backend | `muse-spark-1.3` (conversation). |
| `MODEL_ID_SAFETY` | backend | `muse-wonder-1.0` (safety second opinion). |
| `META_REASONING_EFFORT` | backend | `minimal` (voice latency floor). |
| `META_BASE_URL` | backend | `https://api.meta.ai/v1`. |
| `DEMO_API_TOKEN` | backend | Shared demo Bearer [REDACTED] Set for the public demo. |
| `NEXT_PUBLIC_DEMO_API_TOKEN` | frontend | Same token, build time. |
| `DEMO_RESET_ENABLED` | backend | `1` so judges can reseed; token-gated. |
| `HOST` / `PORT` | backend | `0.0.0.0` / platform port. |
| `PYTHONPATH` | backend, scheduler | `backend`. |
| Twilio vars | backend, scheduler | Only when the phone step is approved. |

Known limits: API auth is a shared demo token (no per-user identity).
Demo data only; nothing sensitive. Trial Twilio (when approved) plays a
trial prompt and only verified numbers can call.

## Owner-approved sequence

1. **Approval:** Railway project + managed Postgres + any charges +
   public domains + exact revision to deploy.
2. Create the project, Postgres plugin, and the three services from the
   approved revision. Set build/start/healthcheck per `railway.toml` files.
3. **Approval:** every env var above. Set them per service.
4. **Approval:** schema creation on the fresh demo database.
   Run `python -m app.database` once in the backend service.
   (`create_all` only creates missing tables; never run on real data.)
5. **Approval:** deploy. Then verify `/health`, `/ready`, and the frontend
   URL. Seed via `POST /demo/reset` + seed, or the documented seed flow.
6. **Separately:** Twilio number, webhooks, billing, live calls.
   Webhook target: `<backend-origin>/phone/inbound`.
