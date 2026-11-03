import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app import meta, safety, spend
from app.main import app


@pytest.mark.parametrize("language", ["en", "es"])
def test_flagged_report_calls_wonder_and_keeps_verification_advice(tmp_path, monkeypatch, language):
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    spend.metadata.create_all(engine)
    monkeypatch.setenv("MODEL_API_KEY", "configured")
    monkeypatch.delenv("MODEL_ID_SAFETY", raising=False)
    monkeypatch.setattr(safety, "get_engine", lambda: engine)
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        content = json.dumps({"verdict": "likely_scam", "signals": ["pressure"], "guidance": "Pause." if language == "en" else "Haga una pausa."})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    transport_client = httpx.Client(transport=httpx.MockTransport(handler))
    original_chat = meta.chat
    monkeypatch.setattr(meta, "chat", lambda messages, **kwargs: original_chat(messages, client=transport_client, **kwargs))
    with TestClient(app) as api:
        response = api.post("/safety/assess", json={"text": "A caller demands immediate payment and a verification code", "language": language})
    assert response.status_code == 200
    result = response.json()
    assert result["verdict"] == "likely_scam" and result["signals"] == ["pressure"]
    assert calls[0]["model"] == "muse-wonder-1.0" and calls[0]["temperature"] == 0
    assert ("independently" if language == "en" else "por su cuenta") in " ".join(result["guidance"])
    assert ("likely" if language == "en" else "probablemente") in " ".join(result["guidance"])
    with engine.connect() as connection:
        row = connection.execute(select(spend.ledger)).mappings().one()
        assert row["status"] == "settled" and row["model"] == "muse-wonder-1.0"
    transport_client.close()
    engine.dispose()


def test_unflagged_and_missing_key_do_not_call_model(monkeypatch):
    monkeypatch.setattr(meta, "chat", lambda *a, **k: pytest.fail("Unexpected model call"))
    monkeypatch.setenv("MODEL_API_KEY", "configured")
    with TestClient(app) as api:
        assert not api.post("/safety/assess", json={"text": "Hello"}).json()["suspicious"]
        monkeypatch.delenv("MODEL_API_KEY")
        result = api.post("/safety/assess", json={"text": "Caller demands immediate payment"}).json()
        assert result["suspicious"] and "verdict" not in result


def test_spend_cap_refuses_without_http(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    spend.metadata.create_all(engine)
    spend.reserve(engine, "muse-spark-1.3", spend.CAP)
    monkeypatch.setenv("MODEL_API_KEY", "configured")
    monkeypatch.setattr(safety, "get_engine", lambda: engine)
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("Unexpected HTTP call"))) as transport_client:
        original_chat = meta.chat
        monkeypatch.setattr(meta, "chat", lambda messages, **kwargs: original_chat(messages, client=transport_client, **kwargs))
        with TestClient(app) as api:
            response = api.post("/safety/assess", json={"text": "Caller demands immediate payment"})
    assert response.status_code == 429
    engine.dispose()
