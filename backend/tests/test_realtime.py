"""Offline relay tests: the browser socket, with Meta faked in-process."""
import asyncio
import json

import pytest
import websockets
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from starlette.websockets import WebSocketDisconnect

from app.database import get_db
from app.main import app
from app.models import Base


class FakeMeta:
    """Scripted Meta endpoint. Preload `events`; the handshake ack is automatic."""

    def __init__(self):
        self.sent = []
        self.events = asyncio.Queue()
        self.recvs = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        self.recvs += 1
        if self.recvs == 1:
            return json.dumps({"sessionId": "test-1"})
        return await self.events.get()

    def __aiter__(self):
        return self

    async def __anext__(self):
        message = await self.events.get()
        if message is None:
            raise StopAsyncIteration
        return message


@pytest.fixture
def relay(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'relay.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    from app import spend
    spend.metadata.create_all(engine)

    def override():
        from sqlalchemy.orm import Session
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr("app.realtime.get_engine", lambda: engine)
    monkeypatch.delenv("DEMO_API_TOKEN", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    fake = FakeMeta()
    monkeypatch.setattr(websockets, "connect", lambda *args, **kwargs: fake)
    with TestClient(app) as client:
        yield client, engine, fake
    app.dependency_overrides.clear()


def test_relay_forwards_audio_and_transcripts(relay):
    client, engine, fake = relay
    fake.events.put_nowait(json.dumps({"type": "transcript", "transcript": "hello", "final": False}))
    fake.events.put_nowait(json.dumps({"type": "speechComplete", "turnId": 1, "transcript": "hello"}))
    with client.websocket_connect("/voice/stream?language=en") as sock:
        assert json.loads(sock.receive_text()) == {"type": "ready"}
        sock.send_bytes(b"\x00\x01" * 8000)
        first = json.loads(sock.receive_text())
        second = json.loads(sock.receive_text())
        assert (first["type"], first["transcript"]) == ("transcript", "hello")
        assert (second["type"], second["transcript"]) == ("speechComplete", "hello")
        sock.send_text('{"type":"endStream"}')
    handshake = json.loads(fake.sent[0])
    assert handshake["authorization"] == {"accessToken": "Bearer test-key"}
    assert handshake["audioEncoding"] == "PCM_16KHZ"
    assert handshake["languageBias"] == ["English"]
    assert fake.sent[1] == b"\x00\x01" * 8000
    from app import spend
    with engine.connect() as conn:
        rows = conn.execute(select(spend.ledger.c.status)).fetchall()
    assert rows and all(row[0] == "settled" for row in rows)


def test_relay_rejects_bad_token(relay, monkeypatch):
    client, engine, fake = relay
    monkeypatch.setenv("DEMO_API_TOKEN", "secret")
    with client.websocket_connect("/voice/stream?token=wrong") as sock:
        with pytest.raises(WebSocketDisconnect):
            sock.receive_text()
