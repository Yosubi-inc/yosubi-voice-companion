import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app import main
from app.meta import model_call
from app.phone import TwilioProvider
from app.resilience import retry


def test_ready_checks_database(monkeypatch):
    engine = create_engine("sqlite://")
    monkeypatch.setattr(main, "get_engine", lambda: engine)
    with TestClient(main.app) as client:
        assert client.get("/ready").status_code == 200
        monkeypatch.setattr(main, "get_engine", lambda: (_ for _ in ()).throw(ConnectionError()))
        assert client.get("/ready").status_code == 503
        assert client.get("/health").status_code == 200
    engine.dispose()


def test_retry_backoff_and_last_error():
    delays = []
    errors = [TimeoutError("first"), TimeoutError("last")]
    def fail():
        raise errors.pop(0)
    with pytest.raises(TimeoutError, match="last"):
        retry(fail, attempts=2, sleep=delays.append, jitter=lambda low, high: high)
    assert delays == [0.2]


def test_retry_succeeds_and_does_not_retry_permanent_errors():
    calls = []
    def operation():
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError()
        return "ok"
    assert retry(operation, sleep=lambda _: None) == "ok"
    assert len(calls) == 2
    with pytest.raises(ValueError):
        retry(lambda: (_ for _ in ()).throw(ValueError()), sleep=lambda _: pytest.fail("retried"))


def test_retry_handles_httpx_transient_errors():
    import httpx
    request = httpx.Request("GET", "http://127.0.0.1/")
    for exc in (httpx.ConnectError("offline", request=request),
                httpx.ReadTimeout("timeout", request=request),
                httpx.HTTPStatusError("busy", request=request,
                                      response=httpx.Response(503, request=request))):
        calls = []
        def operation():
            calls.append(1)
            if len(calls) == 1:
                raise exc
            return "ok"
        assert retry(operation, sleep=lambda _: None) == "ok"
        assert len(calls) == 2
    permanent = httpx.HTTPStatusError("bad request", request=request,
                                      response=httpx.Response(400, request=request))
    with pytest.raises(httpx.HTTPStatusError):
        retry(lambda: (_ for _ in ()).throw(permanent), sleep=lambda _: pytest.fail("retried"))


def test_rate_limit_and_validation(monkeypatch):
    monkeypatch.setattr(main, "RATE_LIMIT", 2)
    with TestClient(main.app) as client:
        response = client.post("/safety/assess", json={"text": "hello", "extra": 1})
        assert response.status_code == 422
        assert set(response.json()["detail"]) == {"en", "es"}
        assert client.get("/guidance/healthcare").status_code == 200
        response = client.get("/guidance/healthcare")
        assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


def test_missing_configuration(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    app = FastAPI()
    app.get("/model")(lambda: model_call(lambda: "never"))
    with TestClient(app) as client:
        response = client.get("/model")
        assert response.status_code == 503 and set(response.json()["detail"]) == {"en", "es"}
    with TestClient(main.app) as client:
        response = client.post("/phone/inbound")
        assert response.status_code == 503 and " / " in response.json()["detail"]
        assert "Traceback" not in response.text


def test_external_seams_retry(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "configured")
    calls = []
    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError()
        return "ok"
    monkeypatch.setattr("app.meta.retry", lambda fn: retry(fn, sleep=lambda _: None))
    assert model_call(flaky) == "ok" and len(calls) == 2
    class Limited(Exception):
        status = 429
    class Calls:
        count = 0
        def create(self, **kwargs):
            self.count += 1
            if self.count == 1:
                raise Limited()
            return SimpleNamespace(sid="call-id")
    provider_calls = Calls()
    monkeypatch.setattr("app.phone.retry", lambda fn, **kw: retry(fn, sleep=lambda _: None, **kw))
    assert TwilioProvider(SimpleNamespace(calls=provider_calls)).place_call(to="a", from_="b", url="c", status_callback="d") == "call-id"
    assert provider_calls.count == 2


def test_request_log_has_no_request_data(caplog):
    with TestClient(main.app) as client:
        response = client.get("/guidance/healthcare?secret=private")
    record = next(json.loads(record.message) for record in caplog.records if record.name == "app.requests")
    assert record == {"request_id": response.headers["X-Request-ID"], "route": "/guidance/healthcare", "outcome": 200}
