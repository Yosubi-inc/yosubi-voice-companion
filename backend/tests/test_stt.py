import io
import json
import subprocess

import imageio_ffmpeg
from email.parser import BytesParser
from email.policy import default
import wave

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app import spend, stt
from app.main import app


@pytest.fixture
def setup_stt(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'stt.db'}")
    spend.metadata.create_all(engine)
    monkeypatch.setattr(stt, "get_engine", lambda: engine)
    monkeypatch.setenv("MODEL_API_KEY", "mock")
    monkeypatch.setenv("META_BASE_URL", "http://mock.invalid/v1")
    yield engine
    engine.dispose()


def audio():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 8000)
    return output.getvalue()


def test_transcribe_and_record_audio_cost(setup_stt, monkeypatch):
    calls = []
    original_client = httpx.Client
    def handler(request):
        calls.append(request)
        assert str(request.url) == "http://mock.invalid/v1/asr/transcribe"
        assert request.headers["accept"] == "application/json"
        message = BytesParser(policy=default).parsebytes(
            b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n" + request.content
        )
        parts = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
        assert set(parts) == {"request", "audio"}
        assert parts["request"].get_content_type() == "application/json"
        assert json.loads(parts["request"].get_payload(decode=True)) == {
            "model": stt.MODEL, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK", "languageBias": ["Spanish"]
        }
        assert parts["audio"].get_content_type() == "audio/wav"
        with wave.open(io.BytesIO(parts["audio"].get_payload(decode=True)), "rb") as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
        return httpx.Response(200, json={"sessionId": "session", "transcript": "Hola", "audioDurationMs": 1000, "turns": []})
    monkeypatch.setattr(stt.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler)))
    response = TestClient(app).post("/stt?language=es", content=audio(), headers={"content-type": "audio/wav"})
    assert response.status_code == 200
    assert response.json() == {"transcript": "Hola", "language": "es", "duration": 1.0}
    assert len(calls) == 1
    with setup_stt.connect() as conn:
        row = conn.execute(select(spend.ledger)).mappings().one()
    assert (row["model"], row["status"], row["cost_microdollars"]) == (stt.MODEL, "settled", 50)


@pytest.mark.parametrize("body,content_type,status", [
    (b"abc", "text/plain", 415),
    (b"abc", "audio/wav", 400),
    (b"x" * (stt.MAX_BYTES + 1), "audio/wav", 413),
], ids=["bad-type", "bad-wav", "oversize"])
def test_bad_audio_is_bilingual(setup_stt, body, content_type, status):
    response = TestClient(app).post("/stt", content=body, headers={"content-type": content_type})
    assert response.status_code == status
    assert set(response.json()["detail"]) == {"en", "es"}


def test_cap_refuses_before_http(setup_stt, monkeypatch):
    spend.reserve(setup_stt, "other", spend.CAP)
    monkeypatch.setattr(stt.httpx, "Client", lambda **kwargs: pytest.fail("unexpected HTTP request"))
    response = TestClient(app).post("/stt", content=audio(), headers={"content-type": "audio/wav"})
    assert response.status_code == 429
    assert set(response.json()["detail"]) == {"en", "es"}


def test_wav_duration_and_truncation():
    from fastapi import HTTPException
    assert stt.audio_duration(audio(), {"wav"}) == 1
    with pytest.raises(HTTPException) as exc:
        stt.audio_duration(audio()[:-10], {"wav"})
    assert exc.value.status_code == 400


def test_mp3_duration():
    # MPEG-1 layer III, 128 kbps, 44.1 kHz: valid fixed-size frames.
    frame = bytes.fromhex("fffb9000") + bytes(413)
    assert stt.audio_duration(frame * 40, {"mp3"}) == pytest.approx(40 * 1152 / 44100, rel=0.02)


def test_webm_duration_from_info_and_opus_blocks():
    import struct
    def element(identifier, body):
        assert len(body) < 127
        return bytes.fromhex(identifier) + bytes([0x80 | len(body)]) + body
    header = element("1a45dfa3", element("4282", b"webm"))
    track = element("ae", element("d7", b"\x01") + element("83", b"\x02") + element("86", b"A_OPUS"))
    tracks = element("1654ae6b", track)
    info = element("1549a966", element("4489", struct.pack(">d", 1000)))
    with_duration = header + element("18538067", info + tracks)
    assert stt.audio_duration(with_duration, {"webm"}) == 1
    block = element("a3", b"\x81\x00\x00\x00\xf8")
    cluster = element("1f43b675", element("e7", b"\x00") + block)
    without_duration = header + element("18538067", tracks + cluster)
    assert stt.audio_duration(without_duration, {"webm"}) == pytest.approx(0.02)


@pytest.mark.parametrize("content_type,extension,codec", [
    ("audio/webm", "webm", "libopus"),
    ("audio/mpeg", "mp3", "libmp3lame"),
])
def test_browser_and_mp3_audio_are_transcoded(setup_stt, monkeypatch, tmp_path, content_type, extension, codec):
    source = tmp_path / "source.wav"
    encoded = tmp_path / ("source." + extension)
    source.write_bytes(audio())
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(source),
                    "-c:a", codec, "-y", str(encoded)], check=True)
    original_run = subprocess.run
    commands = []
    def record_run(command, **kwargs):
        commands.append(command)
        return original_run(command, **kwargs)
    monkeypatch.setattr(stt.subprocess, "run", record_run)
    original_client = httpx.Client
    def handler(request):
        message = BytesParser(policy=default).parsebytes(
            b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n" + request.content
        )
        parts = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
        assert json.loads(parts["request"].get_payload(decode=True))["languageBias"] == ["English"]
        with wave.open(io.BytesIO(parts["audio"].get_payload(decode=True)), "rb") as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
        return httpx.Response(200, json={"transcript": "Hello"})
    monkeypatch.setattr(stt.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler)))
    response = TestClient(app).post("/stt?language=en", content=encoded.read_bytes(), headers={"content-type": content_type})
    assert response.status_code == 200
    assert response.json()["transcript"] == "Hello"
    assert response.json()["language"] == "en"
    assert len(commands) == 1
    assert commands[0][0] == imageio_ffmpeg.get_ffmpeg_exe()
    assert commands[0][commands[0].index("-ar") + 1] == "16000"
    assert commands[0][commands[0].index("-ac") + 1] == "1"


def test_missing_ffmpeg_is_bilingual_503(setup_stt, monkeypatch):
    def unavailable():
        raise RuntimeError("ffmpeg unavailable")
    monkeypatch.setattr(stt.imageio_ffmpeg, "get_ffmpeg_exe", unavailable)
    monkeypatch.setattr(stt.httpx, "Client", lambda **kwargs: pytest.fail("unexpected HTTP request"))
    response = TestClient(app).post("/stt", content=audio(), headers={"content-type": "audio/wav"})
    assert response.status_code == 503
    assert response.json()["detail"] == stt.UNAVAILABLE


@pytest.mark.parametrize("status,body", [(500, {}), (200, {}), (200, {"transcript": None})])
def test_meta_failures_are_bilingual_503(setup_stt, monkeypatch, status, body):
    original_client = httpx.Client
    monkeypatch.setattr(stt.httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body))))
    response = TestClient(app).post("/stt", content=audio(), headers={"content-type": "audio/wav"})
    assert response.status_code == 503
    assert response.json()["detail"] == stt.UNAVAILABLE
