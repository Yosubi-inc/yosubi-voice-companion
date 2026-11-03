# Sparks — hackathon submission package

**Track:** Indie. **Deadline:** November 4, 2026, 8 PM Central.

## Links

- Live demo: `https://sparks-epjn.onrender.com`
- Repo (public): `https://github.com/Yosubi-inc/yosubi-voice-companion` (branch `dev`)
- Demo video: `C:\Users\gabri\projects\sparks-demo.mp4` (3:36, 3.2 MB) — upload to
  YouTube (unlisted) or Drive before submitting; that step needs your account.

## Before judging or recording

Open the live URL and wait ~30 s. The free tier sleeps when idle.

## What Sparks is

- Bilingual EN/ES voice companion for older adults: one big Talk button.
- Live Meta realtime transcription with on-screen captions, EN/ES auto-switch.
- Tasks and reminders with an honest state trail (proposed → scheduled →
  attempted; failures reported, never hidden).
- Scam protection: local signal scan plus a second Meta model verdict.
  Mandatory Medicare scenario verified live in EN and ES.
- Trusted circle with narrow, revocable grants; out-of-scope actions refused.
- Spend ledger: every Model API call logged against the $120 cap.

## Meta usage

- `muse-wonder-1.0` converses (reasoning effort `low`) and judges scams.
- `muse-voice-transcribe-1.0` transcribes live via `/voice/stream` relay.
- Meta MMS (self-hosted) speaks replies; no browser TTS, no third-party voice.

## Evidence

- Backend: 96 pytest green. TTS service: 4 green. Playwright: 23 green.
- Live EN/ES pass (all green): chat EN/ES, task + reminder trail, Medicare
  verdict `scam` EN/ES, benign call not flagged, narrow grant + refusal,
  TTS EN/ES audio, spend ledger, relay ready.
- Settled spend ≈ $0.11 of the $120 working cap.

## Known limits

- Live phone number parked: Twilio trial needs a human signup + number
  purchase. The phone slice is proven by tests only; voice runs in the web app.
- Scheduler marks reminder attempts honestly as failed while no delivery
  channel exists; the trail shows this instead of claiming completion.
