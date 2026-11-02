# yosubi-voice-companion

Bilingual voice assistant for older adults. Meta Global AI Hackathon entry.

## Identity

- Project slug: `yosubi-voice-companion`.
- Repository path: `C:\Users\gabri\projects\yosubi-voice-companion`.
- GitHub repo: not created yet. Local only until the owner approves creation.
- Canonical spec: `SPEC.md` in this repo. Meta docs: https://dev.meta.ai/docs/.

## Success criteria

The ten acceptance tests in `SPEC.md`. Done means all pass on the demo deploy.

## Risk policy

- `production_sensitive: true`. Medium and low risk tasks run without approval.
- High, destructive, database, credential, deploy, and external-send work needs
  the owner (Gabe).

## Check commands

Unknown until the scaffold task defines them. Then: backend tests, frontend
typecheck/lint/tests, voice e2e.

## Deployment boundaries

- Demo deploys to Railway. Any deploy, env var, or domain change needs approval.
- Never expose local services. Loopback only.

## Credential boundaries

- `MODEL_API_KEY` (Meta), Twilio SID/token/number: owner-provisioned into the
  project `.env` (gitignored). Never in code, logs, chat, or artifacts.
- No production Yosubi customer data in this repo, ever.

## Approvals

- Owner: Gabe. One affirmative reply approves the listed rows only.

## Tracking

- Work is tracked as AgentCTL tasks on this project. No second queue.
