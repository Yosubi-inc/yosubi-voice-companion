from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app import meta
from app.main import app


def test_chat_relays_messages_and_requires_demo_auth(monkeypatch):
    credential = uuid4().hex
    monkeypatch.setenv("DEMO_API_TOKEN", credential)
    received = []
    engine = object()
    monkeypatch.setattr("app.main.get_engine", lambda: engine)
    monkeypatch.setattr(meta, "chat", lambda messages, **kwargs: received.append((messages, kwargs)) or "Hola")
    client = TestClient(app)
    payload = {"messages": [{"role": "user", "content": "Hola"}], "language": "es"}
    assert client.post("/chat", json=payload).status_code == 401
    response = client.post("/chat", json=payload, headers={"Authorization": "Bearer " + credential})
    assert response.status_code == 200
    assert response.json() == {"text": "Hola"}
    assert len(received) == 1 and received[0][1] == {"engine": engine}
    sent = received[0][0]
    assert sent[0]["role"] == "system" and "Sparks" in sent[0]["content"]
    assert "jerga" in sent[0]["content"]
    assert sent[1:] == payload["messages"]


@pytest.mark.parametrize("payload", [
    {"messages": []},
    {"messages": [{"role": "invalid", "content": "Hi"}]},
    {"messages": [{"role": "user", "content": ""}]},
    {"messages": [{"role": "user", "content": "Hi"}], "language": "fr"},
])
def test_chat_rejects_invalid_input(monkeypatch, payload):
    monkeypatch.delenv("DEMO_API_TOKEN", raising=False)
    monkeypatch.setattr(meta, "chat", lambda *args, **kwargs: pytest.fail("unexpected model call"))
    response = TestClient(app).post("/chat", json=payload)
    assert response.status_code == 422
    assert set(response.json()["detail"]) == {"en", "es"}


def test_chat_upstream_error_is_bilingual(monkeypatch):
    monkeypatch.delenv("DEMO_API_TOKEN", raising=False)
    monkeypatch.setattr("app.main.get_engine", lambda: None)
    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(meta, "chat", fail)
    response = TestClient(app).post("/chat", json={"messages": [{"role": "user", "content": "Hi"}]})
    assert response.status_code == 503
    assert set(response.json()["detail"]) == {"en", "es"}
