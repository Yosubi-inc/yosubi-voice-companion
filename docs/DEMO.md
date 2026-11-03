# Five-minute demo: Sparks, your community companion

Live demo: `https://yosubi-voice-companion.onrender.com`
All people and records are fictional (seeded persona María Vega).
Have the demo token ready; never show it on screen.
Everything spoken and heard runs on Meta: realtime transcription hears,
Spark converses, Wonder judges scams, and Meta's MMS voice speaks.

## Prepare (5 min before)

1. Wake the demo: open the URL, wait ~30 s for the page (free tier sleeps).
2. Fresh data: `POST /demo/reset` then `POST /demo/seed` with the demo
   Bearer [REDACTED] Note the seeded reminder id from the seed response.
3. Allow the microphone. Keep DevTools closed. Install prompt (phone):
   open in mobile browser, Add to Home Screen, launch as the Sparks app.

## Record

1. **0:00–1:20 — Talk to Sparks.** Press the big Talk button and speak
   naturally: "Hello, I need help with a doctor's appointment." Show the
   live captions appearing as you speak (Meta realtime transcription),
   then Sparks answering in a warm human voice (Meta MMS, not a
   screen-reader voice). Switch mid-talk: "¿Hablas español?" Show the
   language indicator following you.
2. **1:20–2:10 — It remembers and reminds.** Ask "What is my name?" then
   "Remind me to call Elena tomorrow." Show the transcript, the saved
   preference, and the scheduled reminder. Show the seeded reminder's
   state trail (scheduled → attempted) and the honest failure note where
   no delivery channel exists.
3. **2:10–3:20 — Medicare scam flagged live.** Say: "Someone from Medicare
   called demanding payment and my verification code." Show Sparks
   flagging the scam out loud, refusing disclosure, and guiding to
   independent verification. Mention the hybrid safety: Spark converses,
   Wonder (`muse-wonder-1.0`) judges every risky turn.
4. **3:20–4:20 — Trusted circle.** "Let my daughter Elena help with this."
   Show the escalation with consent, her narrow grant, and a refused
   action outside it. Show the resolved informational incident.
5. **4:20–5:00 — Proof, not promises.** `GET /spend/summary`: every Model
   API call logged with tokens and microdollar cost against the $120 cap.
   Close on the installed phone app + the repo link.

## Beats to land (say out loud)

- "Every word I say is transcribed live by Meta."
- "Every reply is spoken by Meta's own voice."
- "Safety is a second Meta model checking the first."
- "The ledger proves what the demo cost."

## Local fallback

If the public demo is unreachable, record against loopback instead:
`DATABASE_URL` to local Postgres, backend on 127.0.0.1:8000, frontend on
127.0.0.1:3000, TTS on 127.0.0.1:8001 (`SERVICE_ROLE=tts`), same steps.
Say so in the video intro.
