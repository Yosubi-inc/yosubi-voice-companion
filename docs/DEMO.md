# Five-minute demo / Demostración de cinco minutos

Live public demo at `<frontend-url>` (API at `<backend-url>`).
All people and records are fictional (seeded persona María Vega).
Have the demo token ready; never show it on screen.

## Prepare

1. Fresh demo data: `POST <backend-url>/demo/reset` with the demo Bearer [REDACTED]
   (needs `DEMO_RESET_ENABLED=1`), then seed per README. Note the reminder id.
2. Open the frontend. Allow the microphone. Keep DevTools closed.

## Record

1. **0:00–1:30 — Live voice conversation.** Press the big button, say
   "Hello, I need help", then "¿Hablas español?". Show the transcript, the
   language indicator switching, and a spoken action confirmation. This runs
   on the live Meta API, not fakes.
2. **1:30–2:30 — Reminder fires.** Show the seeded reminder
   (`GET /reminders/<id>`), wait past its due time, show the scheduler
   attempting it and the state trail proposed → scheduled → attempted.
3. **2:30–3:30 — Medicare scam flagged.** `POST /safety/assess` with the
   Medicare payment + verification-code report, in English and Spanish.
   Show `verdict: scam`, the signals, and the independent-verification
   guidance. Wonder judges, Spark converses.
4. **3:30–4:30 — Trusted contact.** Request escalation to Elena Vega with
   consent; show her narrow grant refusing an incident save; show the
   resolved informational incident.
5. **4:30–5:00 — Spend ledger.** `GET /spend/summary`: every Model API call
   logged with tokens and microdollar cost against the $120 cap.

## Local fallback

If the public demo is unreachable, record against loopback instead:
`DATABASE_URL` to local Postgres, backend on 127.0.0.1:8000, frontend on
127.0.0.1:3000, same steps. Say so in the video intro.
