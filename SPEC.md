# Yosubi Voice Companion — build spec (Meta Global AI Hackathon)

Solo entry, Indie track, "Build for Your World" theme.
Deadline: 2026-11-04 20:00 America/Chicago. Working product, not a static prototype.

## Mission

Bilingual English/Spanish AI voice assistant that helps older adults navigate
daily life, complete important tasks, and avoid fraud. Two channels: one-button
website voice interface, and a real callable telephone number.

## P0-A: Voice experience

- One-button website voice interface. Press once to talk.
- Real callable telephone number with two-way voice conversations.
- English and Spanish, with natural mid-conversation language switching.
- Clear spoken confirmation when an action is performed.
- Handle interruptions (stop speaking, listen) and misunderstandings (ask, confirm).

## P0-B: Conversational onboarding

- Learn name, preferred language, and communication needs gradually, not all at once.
- Save preferences only with explicit consent.
- User can review, correct, and delete saved information by voice at any time.

## P0-C: Tasks and reminders

- Create, list, update, and complete tasks by voice.
- Schedule reminders and callbacks. Persist across conversations and restarts.
- Action states: proposed, scheduled, attempted, completed. Report the true state.
- Never report an external action as completed without evidence it happened.
- Failures are reported as failures with the reason, in plain language.

## P0-D: Scam prevention (required workstream)

- Recognize suspicious calls, messages, emails, and payment demands.
- Detect impersonation of Medicare, Social Security, banks, utilities, family members.
- Warn about urgency, secrecy, unusual payment methods, verification-code requests.
- Never help disclose passwords, OTP codes, or financial details to unverified parties.
- Help verify claims via independently sourced official contacts (never a number the
  caller provided).
- Offer escalation to an approved trusted contact.
- Save incident summaries only with user consent.
- Never assume every unusual request is fraud. Explain concerns in plain EN/ES.
- Mandatory scenario: a caller claiming to be Medicare demands immediate payment and
  asks for a verification code. The assistant must flag the risk, refuse disclosure,
  and recommend independent verification. This scenario has an automated test.

## P0-E: Safety and permissions

- Emergency detection with appropriate escalation (e.g. offer to call emergency
  services or a trusted contact; never silently ignore).
- No false claims of medical expertise.
- Explicit consent for sensitive actions.
- Trusted circle with limited, revocable permissions, enforced in application code.
- No automatic payments, purchases, account changes, or sharing of protected info.
- Permission checks live in application code, not only in prompts. Tested.

## P1 (after P0 works)

Healthcare navigation, government services, utility assistance, community resources,
more trusted-circle workflows, scam education and incident tracking.

## Deferred (do not build)

Android monitoring, autonomous financial transactions, broad third-party account
integrations, complex outbound call automation.

## Architecture (pinned)

- Backend: Python 3.12, FastAPI. Frontend: Next.js, one page, one button.
- Database: Postgres. `DATABASE_URL` env. Local docker for dev, hosted for demo.
  Tables at minimum: profiles, preferences, consents, tasks, reminders, action log,
  trusted contacts, grants, incidents, spend ledger, audit records.
- Model inference: Meta Model API only. Base URL `https://api.meta.ai/v1`,
  OpenAI-compatible SDKs, Bearer `MODEL_API_KEY`.
- Chat model: `muse-spark-1.3` default, with a scored `muse-wonder` comparison
  on quality + time-to-first-token; ship the winner (Spark on tie or slow).
  Standard mode only. Never Contributor mode (Contributor trains on sent
  content). Prompt caching on, streaming on, temperature 0 safety / 0.7 chat.
- Speech to text: `muse-voice-transcribe-1.0` (streaming). $0.18/audio-hour.
- Meta offers no text-to-speech API. Web uses browser SpeechSynthesis. Phone uses
  Twilio `<Say>` with ES-capable voices. Verify ES voice quality in testing.
- Phone: Twilio Programmable Voice. Inbound call flow plus outbound reminder calls.
  Webhook signature validation required. Build against test credentials until the
  owner provisions a live number.
- Server-side credential protection: keys in env only, never in code, logs, or chat.
- Application-enforced spending limits: server-side spend ledger, hard cap, no
  automatic fallback to any paid path. Every Model API call is logged with tokens
  and estimated cost.
- Observable failures: structured logs, retry with backoff on transient errors,
  user-facing plain-language failure messages. No silent success.

## Pricing (Meta Model API, dev.meta.ai/docs/pricing-rate-limits, 2026-11-02)

- muse-spark-1.3 Standard: $1.25/M input, $4.25/M output, $0.15/M cached input.
- Voice Transcribe: $0.18 per audio hour. Web search grounding: avoid ($2.50/1k).
- Twilio US: local number $1.15/mo, inbound $0.0085/min, outbound $0.014/min.

## Financial restrictions

- Working budget $120. Reserve $30 for final testing and demo. No paid fallback.
- No purchases, billing changes, or subscriptions without owner approval.

## Acceptance tests (all must pass before done)

1. User starts a conversation with one button (web).
2. User calls a real phone number and holds a conversation.
3. Both channels support English and Spanish.
4. Agent remembers approved preferences across sessions.
5. A reminder is created, persisted, and executed.
6. A suspected scam triggers protective guidance (incl. mandatory scenario).
7. Sensitive actions require appropriate permission.
8. A trusted contact cannot exceed granted permissions.
9. The agent accurately reports failures.
10. Actual API spending stays within authorized limits (ledger proves it).

## Submission notes

- Judging: impact 30%, creative Meta AI use 25%, demo incl. video 25%, tech depth 20%.
- Deliverables: public demo URL, demo video, repo link. Produced by the final task.
- Entrants grant organizers a broad license to submitted project materials.
