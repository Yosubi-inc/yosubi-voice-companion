# Yosubi Voice Companion

The web demo sends recorded audio to `/stt` and chat turns to `/chat` on the same origin. Build the static frontend with `npm --prefix frontend run build`; FastAPI serves `frontend/out` at `/`. For local frontend development against a separate backend, set `BACKEND_URL` (or `NEXT_PUBLIC_API_BASE`) before starting or building the frontend. Set `DEMO_OFFLINE=1` before starting the frontend to use fakes.

The supervisor can run `python backend/eval_models.py` with a configured backend database and model credential. The live section is marked SUPERVISOR-RUN and skips without the credential. Initialize the spend ledger schema first. Mock tests make no live calls.

## Run and verify

From the repository root in PowerShell:

```powershell
python -m pip install -r requirements.txt
python -m pytest
cd frontend
npm install
npm run typecheck
npm run lint
npm run build
npm run dev
```

Open `http://127.0.0.1:3000`, allow microphone access, and use the button and simulated transcript field. To run browser tests, stop the development server and run:

```powershell
cd e2e
npm install
npx playwright install chromium
npm test
```

Playwright starts the frontend on loopback. The backend health endpoint can be run with `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`.

## Tasks and reminders

Create the development schema with `python -m app.database` (set `PYTHONPATH=backend` and `DATABASE_URL` first). Start the API as above and run the scheduler separately from the repository root:

```powershell
$env:PYTHONPATH = "backend"
python -m app.scheduler
```

The API provides `POST /tasks`, `GET /tasks`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, `POST /tasks/{id}/complete`, `POST /reminders`, and `GET /reminders/{id}`. Supply a task ID, `kind` (`reminder` or `callback`), and an ISO 8601 `due_at` with a time zone. The reminder response includes its recorded history and bilingual failure reasons. The scheduler persists claims before delivery; an interrupted attempt remains attempted and is not automatically repeated. The worker uses the test phone provider when configured as described below; otherwise it reports failure. Integrations can call `run_due(engine, callback)` with a callback that returns evidence or raises `DeliveryFailure` with English and Spanish reasons.

## Safety API

`POST /safety/assess` accepts `text` and `language` (`en` or `es`). Local heuristics check every report. When they flag a possible scam and `MODEL_API_KEY` is set, the endpoint requests a second opinion using `MODEL_ID_SAFETY` (default `muse-wonder-1.0`, temperature 0) through the spend ledger. The response includes the model verdict, signals, and guidance alongside the local warning. Without a key, guidance remains local. Model errors and spend-limit refusals are returned to the caller. It offers direct emergency or trusted-contact escalation, but does not call or message anyone. Heuristics cannot identify every scam or emergency.

Trusted contacts and their `receive_escalation` or `save_incident` grants are managed under `/safety/profiles/{profile_id}`. Each change and sensitive action requires current profile consent and explicit action consent; a contact action also requires an active grant. Incident summaries are saved only through the consent-gated endpoint. Payments, purchases, account changes, and protected-information sharing are not supported.

Contacts can have a `trusted_contact`, `family`, `friend`, or `caregiver` role; roles do not grant permissions. `POST /safety/profiles/{profile_id}/escalations` creates a request for a contact and a specific permission. Both that permission and `receive_escalation` must be granted. `POST /safety/profiles/{profile_id}/escalations/{id}/decision` records an `approved` or `denied` decision, checking both grants again. `GET /safety/profiles/{profile_id}/activity` shows request and decision activity. These records do not send messages or perform the requested action.

`GET /safety/profiles/{profile_id}/incidents` accepts an optional `status` filter (`open`, `in_progress`, or `resolved`). `PATCH /safety/profiles/{profile_id}/incidents/{id}` changes status with explicit consent and, for a contact, an active `save_incident` grant. `GET /safety/lessons?language=en` or `language=es` returns local scam education text.

Set `DEMO_API_TOKEN` in the backend process environment to require `Authorization: Bearer <token>` on profile, conversation, task, reminder, safety, guidance, and trust routes. When unset or empty, these routes remain open and the server logs a startup warning. `/health` remains open; `/phone/*` keeps Twilio signature authentication. The frontend API helper uses `NEXT_PUBLIC_DEMO_API_TOKEN` when set at build time. The web interface calls the backend directly.

The shared demo token is visible to browser users and does not provide individual identity or ownership checks. Use only demo data. Profile IDs and contact IDs are not proof of identity. Use a fresh development database after schema changes: `create_all` does not update existing tables.

`/health` checks only that the process responds; `/ready` also checks database connectivity. API requests are limited to 120 per IP per minute per process; health probes are excluded. The limiter uses the direct peer address, not forwarded headers, and is not shared across workers. Request logs contain only a generated request ID, route template, and status. The model client seam is not connected to an endpoint yet; without `MODEL_API_KEY` it returns a bilingual 503. No model call is made by the existing routes.

The scheduler commits an attempt before calling the provider. A crash can leave an attempt unresolved, even if the call was accepted. Check the provider's records before manually resolving it; do not automatically retry it. Twilio retries only explicit 429 rejections, because retrying a timeout or server error could place a duplicate call. Call acceptance is not proof of delivery.

## Telephone test channel

The phone routes use a local demo agent with the same canned replies as the web fake. `POST /phone/inbound?lang=en` or `?lang=es` starts a speech Gather; turns can switch languages, and saying goodbye ends the call. Every phone webhook, including reminder and status callbacks, requires a Twilio signature. Set `PHONE_WEBHOOK_BASE_URL` to the exact externally configured webhook origin (no trailing path); signatures use that origin and the full path and query. Keep the API on loopback; no tunnel is supplied. Do not trust forwarded host headers.

The scheduler makes test calls only when `PHONE_TEST_MODE=1` and `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `PHONE_TEST_DESTINATION`, and `PHONE_WEBHOOK_BASE_URL` are set in the process environment. Use Twilio test credentials and test phone numbers only. Set `PHONE_LANGUAGE=es` for Spanish reminder calls. Otherwise the scheduler reports a bilingual delivery failure. Call acceptance is recorded as request evidence, not proof that a person answered; status callbacks are authenticated but not persisted. A single configured test destination is shared by reminders; there is no user phone directory.

Spanish uses Twilio `Polly.Mia` with `es-US`; English uses `Polly.Joanna` with `en-US`. The tests verify the requested voice and language in TwiML, not audio quality. Verify Spanish pronunciation and intelligibility with an owner-provisioned live number in a later authorized test; no live call was made here.

### Assistance guidance

`GET /guidance/healthcare`, `/guidance/government`, `/guidance/utilities`, and `/guidance/community` return local guidance. Pass `lang=en` or `lang=es`; the community endpoint also accepts `category`, such as `food`. Example categories are labeled `example` and are not real providers. The `community_resources` table holds local directory entries; create it with the existing `python -m app.database` development schema command. Backend agents can call `healthcare_guidance`, `government_guidance`, `utility_guidance`, and `community_directory` in `app.guidance` directly; the last takes a SQLAlchemy session. No external API is called.
