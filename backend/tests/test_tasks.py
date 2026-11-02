import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import Base
from app.scheduler import DeliveryFailure, run_due


@pytest.fixture
def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def make_reminder(client, delay=0, kind="reminder"):
    task = client.post("/tasks", json={"title": "Take a walk"}).json()
    due = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
    response = client.post("/reminders", json={"task_id": task["id"], "kind": kind, "due_at": due})
    assert response.status_code == 201
    return response.json()["id"]


def test_task_crud(setup):
    client, _ = setup
    response = client.post("/tasks", json={"title": "Call Ana"})
    assert response.status_code == 201
    task_id = response.json()["id"]
    assert client.get("/tasks").json()[0]["title"] == "Call Ana"
    assert client.patch(f"/tasks/{task_id}", json={"title": "Call Luis"}).json()["title"] == "Call Luis"
    assert client.post(f"/tasks/{task_id}/complete").json()["completed"] is True
    assert client.get("/tasks").json()[0]["completed"] is True


def test_scheduler_short_delay_and_restart(setup):
    client, engine = setup
    reminder_id = make_reminder(client, .2, "callback")
    assert run_due(engine, lambda _: "delivered") == 0
    fired = threading.Event()
    def worker():
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if run_due(engine, lambda _: "delivery receipt 123"):
                fired.set()
                return
            time.sleep(.02)
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(4)
    assert fired.is_set()
    engine.dispose()  # A fresh connection sees the persisted result.
    result = client.get(f"/reminders/{reminder_id}").json()
    assert result["state"] == "completed"
    assert result["evidence"] == "delivery receipt 123"
    assert [event["state"] for event in result["history"]] == ["proposed", "scheduled", "attempted", "completed"]
    assert run_due(engine, lambda _: "duplicate") == 0


def test_missing_evidence_and_failure(setup):
    client, engine = setup
    first = make_reminder(client)
    run_due(engine, lambda _: None)
    result = client.get(f"/reminders/{first}").json()
    assert result["state"] == "attempted"
    assert result["status"] == "failed"
    assert result["failure_reason"]["es"] == "No se pudo confirmar la entrega."
    assert "completed" not in [event["state"] for event in result["history"]]
    second = make_reminder(client)
    def fail(_):
        raise DeliveryFailure("The phone is unavailable.", "El teléfono no está disponible.")
    run_due(engine, fail)
    result = client.get(f"/reminders/{second}").json()
    assert result["status"] == "failed"
    assert result["failure_reason"]["en"] == "The phone is unavailable."
    assert result["history"][-1]["state"] == "failed"


def test_persisted_schedule_survives_engine_restart(setup):
    client, engine = setup
    reminder_id = make_reminder(client)
    engine.dispose()
    assert run_due(engine, lambda _: "receipt") == 1
    assert client.get(f"/reminders/{reminder_id}").json()["state"] == "completed"


def test_delete_task(setup):
    client, _ = setup
    task_id = client.post("/tasks", json={"title": "Walk"}).json()["id"]
    assert client.delete(f"/tasks/{task_id}").json() == {"deleted": True}
    assert client.get("/tasks").json() == []
