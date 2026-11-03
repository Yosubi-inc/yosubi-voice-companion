import logging
import secrets

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize("path", ["/profiles/x", "/conversations/x/answer", "/tasks", "/reminders/x", "/safety/lessons", "/guidance/healthcare", "/trust/x"])
def test_protected_paths_reject_missing_and_invalid_credentials(monkeypatch, path):
    token = secrets.token_urlsafe()
    monkeypatch.setenv("DEMO_API_TOKEN", token)
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": f"Bearer {secrets.token_urlsafe()}"}).status_code == 401
        assert client.get("/health").status_code == 200


def test_valid_token_allows_route(monkeypatch):
    token = secrets.token_urlsafe()
    monkeypatch.setenv("DEMO_API_TOKEN", token)
    with TestClient(app) as client:
        assert client.get("/guidance/healthcare", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_unset_token_allows_route_and_warns(monkeypatch, caplog):
    monkeypatch.delenv("DEMO_API_TOKEN", raising=False)
    with caplog.at_level(logging.WARNING), TestClient(app) as client:
        assert client.get("/guidance/healthcare").status_code == 200
    assert "DEMO_API_TOKEN is unset" in caplog.text
