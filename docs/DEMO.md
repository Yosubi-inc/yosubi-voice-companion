# Five-minute demo / Demostración de cinco minutos

All people and records here are fictional. Use a fresh, dedicated local database; do not use customer data. The web transcript and agent are simulated. The web page does not call the backend. The steps below show the web and API separately; no paid API or phone call is needed.

## Prepare / Preparación

From the repository root in PowerShell, install the dependencies from `requirements.txt` and the frontend dependencies as described in README. Use a fresh local SQLite database. Start the API and the frontend in separate PowerShell windows, both bound to loopback:

```powershell
$env:DATABASE_URL = "sqlite:///./demo-local.db"
$env:PYTHONPATH = "backend"
$env:DEMO_RESET_ENABLED = "1"
python backend/seed_demo.py
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm run dev -- --hostname 127.0.0.1
```

The seed schedules its reminder two minutes ahead. Run it shortly before recording. Repeating the seed preserves the existing rows and reminder time. For a fresh run, use the reset below, then seed again. If `DEMO_API_TOKEN` is configured in the API process, send it as a bearer credential in every API request below. The examples assume it is unset in this local demo. Do not record credentials.

In another PowerShell window at the root, find the seeded IDs and prepare the API address:

```powershell
$env:DATABASE_URL = "sqlite:///./demo-local.db"
$env:PYTHONPATH = "backend"
$base = "http://127.0.0.1:8000"
python -c "from app.database import get_engine; from app.models import Reminder, TrustedContact; from sqlalchemy import select; from sqlalchemy.orm import Session; s=Session(get_engine()); print('reminder:', s.scalar(select(Reminder.id))); print('contact:', s.scalar(select(TrustedContact.id).where(TrustedContact.profile_id == 'demo-maria'))); s.close()"
$reminderId = <reminder-id>
$contactId = <contact-id>
```

## Record / Grabar

1. **0:00–1:00 — Web conversation / Conversación web.** Open `http://127.0.0.1:3000`, allow microphone access, and press **Start talking / Empezar a hablar**. In **Fake transcript**, enter `Hello` and send it. Enter `Hola, necesito ayuda` and send it. Show the English and Spanish replies and the language indicator. Audio capture is active but transcription and replies are simulated.
2. **1:00–2:00 — Persona and reminder / Persona y recordatorio.** Show `Invoke-RestMethod "$base/profiles/demo-maria"` and `Invoke-RestMethod "$base/reminders/$reminderId"`. María Vega prefers Spanish and asks for slow, clear speech. After the displayed due time, run the scheduler once with its default local delivery, then show the reminder again:

   ```powershell
   python -c "from app.database import get_engine; from app.scheduler import run_due; print('attempted:', run_due(get_engine()))"
   Invoke-RestMethod "$base/reminders/$reminderId" | ConvertTo-Json -Depth 8
   ```

   The reminder fires as an **attempt**; with no delivery service it reports a bilingual failure. It does not claim a phone call or successful delivery.
3. **2:00–3:00 — Medicare scam / Estafa de Medicare.** Run the local safety check in both languages. Show `suspicious`, the verification-code signal, and the guidance to avoid payment or disclosure and independently verify the claim.

   ```powershell
   Invoke-RestMethod -Method Post -Uri "$base/safety/assess" -ContentType "application/json" -Body (@{text="A caller claiming to be Medicare demands immediate payment and asks for a verification code."; language="en"} | ConvertTo-Json) | ConvertTo-Json -Depth 8
   Invoke-RestMethod -Method Post -Uri "$base/safety/assess" -ContentType "application/json" -Body (@{text="Una llamada dice ser de Medicare y exige pago inmediato y pide un código de verificación."; language="es"} | ConvertTo-Json) | ConvertTo-Json -Depth 8
   ```
4. **3:00–4:30 — Trusted contact / Contacto de confianza.** Elena Vega has only the `receive_escalation` grant. With explicit consent, request guidance to contact her directly. Show that a request to save an incident using her contact ID is denied; her grant does not allow it. Show the resolved informational incident. No message is sent.

   ```powershell
   Invoke-RestMethod -Method Post -Uri "$base/safety/profiles/demo-maria/escalation" -ContentType "application/json" -Body (@{consent=$true; contact_id=$contactId} | ConvertTo-Json)
   try { Invoke-RestMethod -Method Post -Uri "$base/safety/profiles/demo-maria/incidents" -ContentType "application/json" -Body (@{consent=$true; contact_id=$contactId; summary="Demo"} | ConvertTo-Json) } catch { $_.ErrorDetails.Message }
   Invoke-RestMethod "$base/safety/profiles/demo-maria/incidents?status=resolved" | ConvertTo-Json -Depth 8
   ```
5. **4:30–5:00 — Reset / Reinicio.** Reset removes the seeded persona and its linked records, including reminder history. It refuses unless `DEMO_RESET_ENABLED=1`; when `DEMO_API_TOKEN` is configured, the matching bearer credential is also required. It does not recreate the seed.

   ```powershell
   Invoke-RestMethod -Method Post -Uri "$base/demo/reset"
   python backend/seed_demo.py
   ```

Use the credential configured in the API process as `Authorization: Bearer <demo-token>` when needed. Never put it in a recording, script, or repository file.
