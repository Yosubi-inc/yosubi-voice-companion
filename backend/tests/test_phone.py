import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import Base, Reminder, Task
from app.phone import TwilioProvider, reminder_delivery
from app.scheduler import run_due


@pytest.fixture
def setup(tmp_path, monkeypatch):
    token = secrets.token_hex(24)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", token)
    monkeypatch.setenv("PHONE_WEBHOOK_BASE_URL", "http://testserver")
    engine = create_engine(f"sqlite:///{tmp_path / 'phone.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, engine, token
    app.dependency_overrides.clear()
    engine.dispose()


def signed_post(client, token, path, params):
    payload = "http://testserver" + path + "".join(k + params[k] for k in sorted(params))
    sig = base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    return client.post(path, content=urlencode(params), headers={"X-Twilio-Signature": sig, "Content-Type": "application/x-www-form-urlencoded"})


@pytest.mark.parametrize("lang,question,answer,bye,expected,voice", [
    ("en", "hello", "demo action", "goodbye", "Demo action completed", "en-US"),
    ("es", "hola", "acción de prueba", "adiós", "Acción de prueba completada", "es-US"),
])
def test_replayed_call(setup, lang, question, answer, bye, expected, voice):
    client, _, token = setup
    start = signed_post(client, token, f"/phone/inbound?lang={lang}", {"CallSid": "fixture-call"})
    assert start.status_code == 200
    root = ET.fromstring(start.text)
    assert root.find("Gather/Say").attrib["language"] == voice
    path = root.find("Gather").attrib["action"]
    reply = signed_post(client, token, path, {"CallSid": "fixture-call", "SpeechResult": question})
    assert ET.fromstring(reply.text).find("Gather/Say") is not None
    reply = signed_post(client, token, path, {"CallSid": "fixture-call", "SpeechResult": answer})
    assert expected in reply.text
    end = signed_post(client, token, path, {"CallSid": "fixture-call", "SpeechResult": bye})
    assert ET.fromstring(end.text).find("Hangup") is not None


@pytest.mark.parametrize("path", ["/phone/inbound", "/phone/turn?lang=es", "/phone/reminder/1", "/phone/status"])
def test_invalid_signatures_rejected(setup, path):
    client, _, _ = setup
    assert client.post(path, data={"CallSid": "fixture-call"}, headers={"X-Twilio-Signature": "invalid"}).status_code == 403


def test_scheduled_call_and_signed_reminder(setup):
    client, engine, token = setup
    with Session(engine) as db:
        task = Task(title="Take a walk", completed=False)
        db.add(task)
        db.flush()
        reminder = Reminder(task_id=task.id, kind="reminder", due_at=datetime.now(timezone.utc).replace(tzinfo=None), state="scheduled")
        db.add(reminder)
        db.commit()
        reminder_id = reminder.id
    class Calls:
        def create(self, **kwargs):
            self.arguments = kwargs
            return type("Call", (), {"sid": "fixture-call-id"})()
    calls = Calls()
    provider = TwilioProvider(type("Client", (), {"calls": calls})())
    deliver = reminder_delivery(provider, to="+15005550006", from_="+15005550006", base_url="http://testserver", lang="es")
    assert run_due(engine, deliver) == 1
    assert calls.arguments["url"] == f"http://testserver/phone/reminder/{reminder_id}?lang=es"
    assert calls.arguments["status_callback"] == "http://testserver/phone/status"
    assert client.get(f"/reminders/{reminder_id}").json()["evidence"] == "Call request accepted: fixture-call-id"
    response = signed_post(client, token, f"/phone/reminder/{reminder_id}?lang=es", {"CallSid": "fixture-call"})
    assert "Recordatorio: Take a walk" in response.text
    assert signed_post(client, token, "/phone/status", {"CallStatus": "completed"}).status_code == 204
