"""Offline TTS contract tests with the voice model faked."""
import math
import struct
import wave
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from tts import app as tts_app


class FakeTensor(list):
    def numpy(self):
        import numpy as np
        return np.array(self, dtype=float)


class FakeModel:
    def __call__(self, **kwargs):
        frames = 2205
        samples = FakeTensor(10000 * math.sin(2 * math.pi * 440 * t / 22050) / 32767 for t in range(frames))

        class Out:
            pass

        out = Out()
        out.waveform = [samples]
        return out


class FakeTokenizer:
    def __call__(self, text, return_tensors=None):
        return {"input_ids": [[1]]}


@pytest.fixture
def tts_client(monkeypatch):
    monkeypatch.setattr(tts_app, "model_for", lambda language: (FakeTokenizer(), FakeModel()))
    monkeypatch.delenv("DEMO_API_TOKEN", raising=False)
    tts_app._cache.clear()
    with TestClient(tts_app.app) as client:
        yield client


def test_health(tts_client):
    assert tts_client.get("/health").json() == {"status": "ok"}


def test_speak_returns_wav(tts_client):
    response = tts_client.post("/tts", json={"text": "Hello.", "language": "en"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    with wave.open(BytesIO(response.content), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 22050)
        assert wav.getnframes() == 2205


def test_speak_validates_input(tts_client):
    assert tts_client.post("/tts", json={"text": "", "language": "en"}).status_code == 422
    assert tts_client.post("/tts", json={"text": "Hi", "language": "fr"}).status_code == 422


def test_speak_requires_token(monkeypatch):
    monkeypatch.setattr(tts_app, "model_for", lambda language: (FakeTokenizer(), FakeModel()))
    monkeypatch.setenv("DEMO_API_TOKEN", "secret")
    with TestClient(tts_app.app) as client:
        assert client.post("/tts", json={"text": "Hi", "language": "en"}).status_code == 401
        ok = client.post("/tts", json={"text": "Hi", "language": "en"}, headers={"Authorization": "Bearer secret"})
        assert ok.status_code == 200
