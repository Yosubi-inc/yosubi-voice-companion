import json
import math

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select

from app import meta, spend


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    spend.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "configured")
    monkeypatch.delenv("MODEL_ID", raising=False)
    monkeypatch.delenv("META_BASE_URL", raising=False)


def rows(engine):
    with engine.connect() as conn:
        return conn.execute(select(spend.ledger).order_by(spend.ledger.c.id)).mappings().all()


def test_chat_payload_and_usage(engine, monkeypatch):
    monkeypatch.setenv("MODEL_ID", "muse-wonder-1.0")
    messages = [{"role": "system", "content": "Stable instructions"}, {"role": "user", "content": "Hello"}]
    def handler(request):
        assert str(request.url) == "https://api.meta.ai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer configured"
        body = json.loads(request.content)
        assert body == {"model": "muse-wonder-1.0", "messages": messages, "temperature": 0, "stream": False, "max_tokens": 1024, "reasoning_effort": "minimal"}
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hi"}}], "usage": {"prompt_tokens": 100, "completion_tokens": 10, "prompt_tokens_details": {"cached_tokens": 20}}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert meta.chat(messages, engine=engine, client=client, temperature=0) == "Hi"
    row = rows(engine)[0]
    assert (row["status"], row["input_tokens"], row["cached_tokens"], row["output_tokens"], row["cost_microdollars"]) == ("settled", 100, 20, 10, 600)


def test_reasoning_effort_override(engine, monkeypatch):
    bodies = []
    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hi"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        meta.chat([{"role": "user", "content": "Hi"}], engine=engine, client=client, reasoning_effort="low")
        monkeypatch.setenv("META_REASONING_EFFORT", "low")
        meta.chat([{"role": "user", "content": "Hi"}], engine=engine, client=client)
    assert [b["reasoning_effort"] for b in bodies] == ["low", "low"]


def test_stream_retries_and_settles(engine, monkeypatch):
    monkeypatch.setattr(meta, "retry", lambda fn: __import__("app.resilience", fromlist=["retry"]).retry(fn, sleep=lambda _: None))
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"Ho"}}]}\n\ndata: {"choices":[{"delta":{"content":"la"}}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":100,"completion_tokens":4,"prompt_tokens_details":{"cached_tokens":20}}}\n\ndata: [DONE]\n\n')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = meta.chat([{"role": "user", "content": "Hola"}], engine=engine, client=client, stream=True)
        assert next(result) == "Ho"
        assert next(result) == "la"
        assert list(result) == []
    assert len(calls) == 2
    assert calls[1]["model"] == "muse-spark-1.3"
    assert calls[1]["stream_options"] == {"include_usage": True}
    first, second = rows(engine)
    assert first["status"] == "reserved"
    assert (second["status"], second["cost_microdollars"], second["input_tokens"], second["cached_tokens"], second["output_tokens"]) == ("settled", 120, 100, 20, 4)


def test_stream_without_usage_settles_estimate(engine):
    messages = [{"role": "user", "content": "Hola"}]
    text = 'data: {"choices":[{"delta":{"content":"Ho"}}]}\n\ndata: {"choices":[{"delta":{"content":"la"}}]}\n\ndata: [DONE]\n\n'
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=text))) as client:
        assert "".join(meta.chat(messages, engine=engine, client=client, stream=True)) == "Hola"
    row = rows(engine)[0]
    want_in = max(1, math.ceil(len(json.dumps(messages)) / 4))
    want_out = max(1, math.ceil(len("Hola") / 4))
    assert (row["status"], row["input_tokens"], row["output_tokens"]) == ("settled", want_in, want_out)


def test_cap_and_missing_key_stop_before_http(engine, monkeypatch):
    def handler(request):
        pytest.fail("HTTP must not be called")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.delenv("MODEL_API_KEY")
        with pytest.raises(HTTPException) as exc:
            meta.chat([], engine=engine, client=client)
        assert exc.value.status_code == 503 and set(exc.value.detail) == {"en", "es"}
        assert rows(engine) == []
        monkeypatch.setenv("MODEL_API_KEY", "configured")
        spend.reserve(engine, "muse-spark-1.3", spend.CAP)
        with pytest.raises(HTTPException) as exc:
            meta.chat([], engine=engine, client=client)
        assert exc.value.status_code == 429 and set(exc.value.detail) == {"en", "es"}


def test_interrupted_stream_keeps_reservation(engine):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text='data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'))) as client:
        stream = meta.chat([], engine=engine, client=client, stream=True)
        assert next(stream) == "Hi"
        with pytest.raises(ValueError, match="ended before completion"):
            next(stream)
    assert rows(engine)[0]["status"] == "reserved"
