# Yosubi Voice Companion

This scaffold provides a health endpoint and a one-page shell. Voice features are not implemented.

## Backend (Python 3.12)

From the repository root in PowerShell:

```powershell
py -3.12 -m venv backend/.venv
./backend/.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "<postgresql+psycopg URL>"
$env:PYTHONPATH = "backend"
python -m app.database
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Provide a local Postgres database URL in the environment. `app.database` creates the development schema with SQLAlchemy `create_all`; it is not a migration tool. The endpoint is `http://127.0.0.1:8000/health`.

Run backend tests from the root:

```powershell
python -m pytest
```

## Frontend and smoke test

In a separate PowerShell window:

```powershell
cd frontend
npm install
npm run typecheck
npm run lint
npm run build
npm run dev
```

Open `http://127.0.0.1:3000`. For the smoke test, stop the development server first, then from the repository root:

```powershell
cd e2e
npm install
npx playwright install chromium
npm test
```

Playwright starts and stops the frontend server itself. The button is disabled until voice is implemented.
