# Onboarding API

Set `DATABASE_URL` to a local PostgreSQL database URL, then run from the repository root:

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = "backend"
python -m app.database
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`create_all` creates missing tables; it does not alter existing tables. Use a fresh development database when the scaffold schema already exists. Run `python -m pytest` from the repository root. Tests use an in-memory SQLite database and make no paid API calls.

The caller supplies a stable profile identifier. `POST /profiles/{profile_id}/conversations` starts a conversation and returns saved values and the next field. Send one answer at a time to `PUT /conversations/{session_id}/answer` with `field` and `value`; language values are `en` or `es`. Answers remain in memory until saved. Record explicit permission with `PUT /profiles/{profile_id}/consent` and `{"granted": true}`, then call `POST /conversations/{session_id}/save`. Consent can be revoked with `false`; subsequent saves and corrections are refused.

Use `GET /profiles/{profile_id}` to review, `PATCH /profiles/{profile_id}` with `field` and `value` to correct, and `DELETE /profiles/{profile_id}` to delete saved information and active drafts. Application errors contain English and Spanish text. Conversation drafts are process-local and do not survive a restart; saved data does. These endpoints require a trusted caller to establish profile identity; authentication is not provided by this scaffold.
