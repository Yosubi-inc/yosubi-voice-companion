# Demo hosting, part 2: web service on Render

Live: https://yosubi-voice-companion.onrender.com
(Service `srv-dbkpnmou01pc73e05aig`, region Oregon, plan free, branch `dev`.)

Why Render: Meta's model API answers **404 to every request from
Railway's network** (both regions, any key, IPv4 and IPv6), while the same
requests from a laptop, GitHub Actions, or Render behave normally.
Postgres and the reminder scheduler stay on Railway (neither calls Meta);
only this web service moved. Verified 2026-11-03: fake key from Railway
gets 404, from GitHub Actions gets 401, real key from Render gets 200.

## How it was created (API, not Blueprint)

Blueprint creation via API proved fussy, so the service was created
directly: `POST /v1/services` (type `web_service`, runtime `docker`,
dockerfilePath `./Dockerfile`, plan `free`, healthCheckPath `/health`,
branch `dev`, autoDeploy yes). Two API gotchas, both verified:

- `envVars` in the create call are **ignored**. Set them afterwards with
  `PUT /v1/services/{id}/env-vars` (full replacement list).
- The PUT does **not** trigger a deploy. Fire one with
  `POST /v1/services/{id}/deploys`.

`render.yaml` is kept as documentation of the intended shape; the live
service was not created from it.

## Wiring

- `DATABASE_URL`: Railway Postgres **public** proxy URL
  (`shuttle.proxy.rlwy.net:44225`). Public Networking must stay enabled
  on the Railway plugin. Password has no URL-unsafe characters (verified);
  if Railway ever rotates it to one with `@:/?#%`, URL-encode user/password.
- `MODEL_API_KEY`: Meta key (same value as local `.env`).
- `DEMO_API_TOKEN` + `NEXT_PUBLIC_DEMO_API_TOKEN`: fresh Render-only token
  (same value twice; the `NEXT_PUBLIC_` copy bakes into the static export
  at Docker build time — verified present in the served JS bundle).
- `SERVICE_ROLE=web`, `MODEL_ID=muse-spark-1.3`,
  `MODEL_ID_SAFETY=muse-wonder-1.0`, `META_BASE_URL`, `META_REASONING_EFFORT=minimal`,
  `DEMO_RESET_ENABLED=1`.

Secrets live in gitignored `.env.render` (plus `RENDER_API_KEY` for API
driving). Never commit, never paste into chat.

## Operate

- Deploy: push to `dev` (autoDeploy) or `POST /v1/services/{id}/deploys`.
  Poll `GET .../deploys/{depId}` (single object, `.status`) to `live`.
- Seed: `POST /demo/seed` (Bearer token). Same shared Postgres as
  Railway, so the demo persona persists across hosts.
- Spend: `GET /spend/summary` (Bearer token).
- Logs: Render dashboard, or `GET /v1/services/{id}/logs`.
- The old Railway backend still serves the page but its `/chat` 503s
  (Meta 404). Delete it after judging, or keep as a spare static page.

## Notes

- Render free web services sleep when idle; first request wakes in ~30 s.
  Wake it before recording or judging.
- Scheduler stays on Railway on the private URL. Seeded reminders show
  `attempted → failed` with "No delivery service is configured": honest
  failure reporting, per spec (no delivery channel exists while Twilio is
  parked).
- Speech-to-text uses Meta's file endpoint `POST /asr/transcribe`
  (multipart `request` + `audio`, WAV 16/24 kHz mono); see
  `backend/app/stt.py`. OpenAI-style `/audio/transcriptions` 404s.
