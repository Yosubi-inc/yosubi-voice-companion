# Demo deployment runbook (Railway)

> 2026-11-03: Meta's API 404s all Railway-egress traffic, so the web
> service moves to Render. This file stays for Postgres + scheduler.
> Web-service steps: [DEPLOY_RENDER.md](DEPLOY_RENDER.md).

Target: public demo for hackathon judging (Nov 4-8). One image, two
services, managed Postgres, all from this repo's `dev` branch.

Public demo: https://backend-production-71926.up.railway.app
(Project: `yosubi-voice-companion-demo`.)

Shape: the backend container serves the statically exported Next.js page
same-origin (`/` + API on one host, no CORS, no proxy service).

Services:

- `backend` (`SERVICE_ROLE=web`): Dockerfile at repo root, start
  `./start.sh` (uvicorn on `0.0.0.0:$PORT`). Public domain above.
- `scheduler` (`SERVICE_ROLE=scheduler`): same image. Boot runs
  `python -m app.database` (idempotent `create_all`), then
  `python -m app.scheduler` (`run_due` loop, no HTTP).
- `postgres`: Railway managed plugin. Both services reference
  `${{Postgres.DATABASE_URL}}` (private networking).

No healthcheck gate in `railway.toml`: the scheduler serves no HTTP, and
the gate would apply to both roles. Verify by hand instead (`/health`,
`/ready`, `/`).

Environment variables (Railway service variables, never in files):

| Variable | Services | Notes |
| --- | --- | --- |
| `DATABASE_URL` | backend, scheduler | `${{Postgres.DATABASE_URL}}` reference. |
| `MODEL_API_KEY` | backend, scheduler | Meta Model API key. Server-side only. Set via `variable set --stdin`. |
| `MODEL_ID` | backend, scheduler | `muse-spark-1.3` (conversation). |
| `MODEL_ID_SAFETY` | backend | `muse-wonder-1.0` (safety second opinion). |
| `META_REASONING_EFFORT` | backend, scheduler | `minimal` (voice latency floor). |
| `META_BASE_URL` | backend, scheduler | `https://api.meta.ai/v1`. |
| `DEMO_API_TOKEN` | backend | Shared demo Bearer [REDACTED] Runtime auth. |
| `NEXT_PUBLIC_DEMO_API_TOKEN` | backend | Same token; baked into the static export at Docker build time. |
| `DEMO_RESET_ENABLED` | backend | `1`; gates `/demo/seed` + `/demo/reset` (both token-gated). |
| `SERVICE_ROLE` | backend=`web`, scheduler=`scheduler` | Picks the `start.sh` branch. |
| Twilio vars | — | Parked. Only when the phone step is approved. |

Known limits: API auth is a shared demo token (no per-user identity).
Demo data only; nothing sensitive.

## Operate

- Deploy: push to `dev`; both services auto-deploy the same image.
- Schema: automatic on scheduler boot. Never run `create_all` on real data.
- Seed: `POST /demo/seed` (Bearer token). Idempotent; `{"created": false}`
  when the demo persona already exists. To reseed: `POST /demo/reset`
  clears the demo persona, then `POST /demo/seed` restores it.
- Spend: `GET /spend/summary` (Bearer token). Cap $120 working + $30
  reserve of the $150 promo credits.
- Logs: `railway logs -s backend|scheduler` (note: CLI log tailing is
  flaky; the dashboard is the fallback).
- Shell into a service (`railway ssh`) needs clean Windows OpenSSH
  permissions on `~/.ssh/config`; inherited sandbox ACEs break it.
  Prefer the HTTP operate paths above.

## Phone (parked)

Twilio trial signup, number, webhooks, billing, live calls are on hold.
When approved, webhook target: `<backend-origin>/phone/inbound`.
