# Demo hosting, part 2: web service on Render (morning of Nov 3)

Deadline: Nov 4, 8 PM CT. The Railway deploy is up but Meta's model API
answers **404 to every request from Railway's network** (both regions, any
key, IPv4 and IPv6), so chat and transcription cannot serve from there.
Same requests from a laptop or GitHub Actions behave normally (401 with a
bad key, 200 with the real key). Fix: move only the web service to Render.
Postgres and the reminder scheduler stay on Railway (neither calls Meta).

## Owner steps (about 15 minutes, no CLI)

1. Railway dashboard → project `yosubi-voice-companion-demo` → Postgres
   plugin → Settings → enable **Public Networking**. Copy the public
   `DATABASE_URL` (it has the form `postgresql://...@...proxy.rlwy.net:port/railway`).
2. Generate a fresh demo token on your own machine (do not reuse the
   Railway one and do not paste secrets into chat):
   `openssl rand -hex 24` (or 32 random letters/digits).
3. Sign in to Render with GitHub, **New → Blueprint**, pick repo
   `Yosubi-inc/yosubi-voice-companion` (branch `dev`, `render.yaml`).
4. Fill the four `sync: false` values when Render asks:
   - `DATABASE_URL`: the Railway public URL from step 1.
   - `MODEL_API_KEY`: the Meta key (same one as local `.env`).
   - `DEMO_API_TOKEN` and `NEXT_PUBLIC_DEMO_API_TOKEN`: the fresh token
     from step 2 (same value twice).
5. Deploy. First build takes ~10 minutes (Next.js export + pip install).
   Health check is `/health`.

## Supervisor verify (after Render is green)

```powershell
$base = "<render-web-url>"
$tok = "<fresh-demo-token>"  # owner provides at that moment, never stored
Invoke-WebRequest "$base/health" -UseBasicParsing
Invoke-WebRequest "$base/" -UseBasicParsing          # exported page, ~5 KB
Invoke-WebRequest "$base/demo/seed" -Method POST -Headers @{Authorization="Bearer $tok"} -UseBasicParsing
curl.exe -s -m 90 -X POST "$base/chat" -H "Authorization: Bearer $tok" `
  -H "Content-Type: application/json" -d "@C:\tmp\chat_en.json"
```

Expect: `{"status":"ok"}`, the page, `{"created":true,...}`, and a real
model reply. If `/chat` still 503s, read the backend log line
`chat upstream failed:` — it names the exception class and Meta status.

## Notes

- Render free web services sleep when idle; first request wakes in ~30 s.
  Fine for judging; wake it before recording.
- Scheduler stays on Railway, talking to Postgres over the private URL.
  Schema creation runs on scheduler boot; nothing to redo.
- The old Railway backend service can stay (it serves the page but its
  `/chat` 503s) or be deleted after Render verifies. Decide at handoff.
- `start.sh`/`Dockerfile` needed no changes: Render injects `$PORT` and
  uses the image `CMD`, same as Railway.
