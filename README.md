# Yosubi Voice Companion

The web demo captures microphone audio and sends chunks to a fake streaming STT adapter. It does not transcribe audio: enter a simulated transcript in the labeled field. The fake agent responds in English or Spanish; say or type “demo action” / “acción de prueba” for a spoken simulated action confirmation. No real external action is performed. New transcripts interrupt speech. Stop releases the microphone. No API key is needed.

`frontend/lib/voice.ts` defines streaming transcription and chat-completion-shaped agent interfaces for later live integration. The fakes make no network calls.

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

The API provides `POST /tasks`, `GET /tasks`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, `POST /tasks/{id}/complete`, `POST /reminders`, and `GET /reminders/{id}`. Supply a task ID, `kind` (`reminder` or `callback`), and an ISO 8601 `due_at` with a time zone. The reminder response includes its recorded history and bilingual failure reasons. The scheduler persists claims before delivery; an interrupted attempt remains attempted and is not automatically repeated. Its default delivery callback reports failure because no delivery service is configured. Integrations can call `run_due(engine, callback)` with a callback that returns delivery evidence or raises `DeliveryFailure` with English and Spanish reasons. No phone call is made by the default worker.

## Safety API

`POST /safety/assess` accepts `text` and `language` (`en` or `es`). It returns local scam and emergency guidance; no model call is made. It offers direct emergency or trusted-contact escalation, but does not call or message anyone. Heuristics cannot identify every scam or emergency.

Trusted contacts and their `receive_escalation` or `save_incident` grants are managed under `/safety/profiles/{profile_id}`. Each change and sensitive action requires current profile consent and explicit action consent; a contact action also requires an active grant. Incident summaries are saved only through the consent-gated endpoint. Payments, purchases, account changes, and protected-information sharing are not supported.

The scaffold has no authentication. Profile IDs and contact IDs are not proof of identity. Keep this API local and add authenticated identity and ownership checks before exposing it to users. Use a fresh development database after schema changes: `create_all` does not update existing tables.
