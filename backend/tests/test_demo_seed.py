import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import ActionLog, Base, Consent, DemoSeed, Grant, Incident, Preference, Profile, Reminder, Task, TrustedContact
from seed_demo import PROFILE_ID, seed


@pytest.fixture
def demo(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}", connect_args={"check_same_thread": False})
    seed(engine)
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    monkeypatch.delenv("DEMO_API_TOKEN", raising=False)
    monkeypatch.delenv("DEMO_RESET_ENABLED", raising=False)
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def test_seed_is_idempotent_and_complete(demo):
    _, engine = demo
    models = (Profile, Preference, Consent, Task, Reminder, ActionLog, TrustedContact, Grant, Incident, DemoSeed)
    def snapshot():
        with Session(engine) as db:
            return {model.__name__: [tuple(row) for row in db.execute(select(model.__table__)).all()] for model in models}
    before = snapshot()
    seed(engine)
    assert snapshot() == before
    with Session(engine) as db:
        assert db.get(Profile, PROFILE_ID).name == "María Vega"
        pref = db.get(Preference, PROFILE_ID)
        assert pref.preferred_language == "es" and pref.communication_needs
        assert db.get(Consent, PROFILE_ID).granted
        assert not db.scalar(select(Task)).completed
        reminder = db.scalar(select(Reminder))
        assert reminder.state == "scheduled" and reminder.due_at > datetime.now(timezone.utc).replace(tzinfo=None)
        assert db.scalar(select(Grant)).permission == "receive_escalation"
        assert db.scalar(select(Incident)).status == "resolved"


def test_reset_gating_and_scoped_deletion(demo, monkeypatch):
    client, engine = demo
    with Session(engine) as db:
        db.add_all([Profile(id="other", name="Other"), Task(title="Other", completed=False)])
        db.commit()
    assert client.post("/demo/reset").status_code == 403
    monkeypatch.setenv("DEMO_RESET_ENABLED", "1")
    token = secrets.token_urlsafe(24)
    monkeypatch.setenv("DEMO_API_TOKEN", token)
    assert client.post("/demo/reset").status_code == 401
    assert client.post("/demo/reset", headers={"Authorization": "Bearer " + token + "x"}).status_code == 401
    with Session(engine) as db:
        assert db.get(Profile, PROFILE_ID) is not None
    assert client.post("/demo/reset", headers={"Authorization": "Bearer " + token}).status_code == 200
    with Session(engine) as db:
        assert db.get(Profile, PROFILE_ID) is None
        assert db.get(Profile, "other") is not None
        assert list(db.scalars(select(Task.title))) == ["Other"]
        for model in (DemoSeed, Reminder, ActionLog, Grant, Incident, TrustedContact):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert client.post("/demo/reset", headers={"Authorization": "Bearer " + token}).status_code == 200
    seed(engine)
    monkeypatch.delenv("DEMO_API_TOKEN")
    assert client.post("/demo/reset").status_code == 200


def test_seed_gating_and_idempotent_reseed(demo, monkeypatch):
    client, engine = demo
    assert client.post("/demo/seed").status_code == 403
    monkeypatch.setenv("DEMO_RESET_ENABLED", "1")
    token = secrets.token_urlsafe(24)
    monkeypatch.setenv("DEMO_API_TOKEN", token)
    assert client.post("/demo/seed").status_code == 401
    headers = {"Authorization": "Bearer " + token}
    assert client.post("/demo/seed", headers=headers).json()["created"] is False
    assert client.post("/demo/reset", headers=headers).status_code == 200
    with Session(engine) as db:
        assert db.get(Profile, PROFILE_ID) is None
    response = client.post("/demo/seed", headers=headers)
    assert response.status_code == 200 and response.json()["created"] is True
    with Session(engine) as db:
        assert db.get(Profile, PROFILE_ID) is not None
        assert db.get(DemoSeed, PROFILE_ID) is not None


def test_script_runs_twice(tmp_path):
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'script.db'}"
    for _ in range(2):
        subprocess.run([sys.executable, "backend/seed_demo.py"], env=env, check=True)
    engine = create_engine(env["DATABASE_URL"])
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DemoSeed)) == 1
        assert db.scalar(select(func.count()).select_from(Reminder)) == 1
    engine.dispose()
