import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app import main, spend


@pytest.fixture
def setup_summary(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    spend.metadata.create_all(engine)
    monkeypatch.setattr(main, "get_engine", lambda: engine)
    credential = secrets.token_urlsafe()
    monkeypatch.setenv("DEMO_API_TOKEN", credential)
    with TestClient(main.app) as client:
        yield client, engine, {"Authorization": f"Bearer {credential}"}
    engine.dispose()


def test_summary_requires_demo_auth(setup_summary):
    client, _, headers = setup_summary
    for supplied in ({}, {"Authorization": f"Bearer {secrets.token_urlsafe()}"}):
        response = client.get("/spend/summary", headers=supplied)
        assert response.status_code == 401
        assert set(response.json()["detail"]) == {"en", "es"}
    assert client.get("/spend/summary", headers=headers).status_code == 200


def test_empty_summary(setup_summary):
    client, _, headers = setup_summary
    assert client.get("/spend/summary", headers=headers).json() == {
        "cap_microdollars": 120_000_000,
        "totals": {"reserved_microdollars": 0, "settled_microdollars": 0},
        "per_model": [], "recent_entries": [],
    }


def test_summary_totals_recent_limit_and_read_only(setup_summary):
    client, engine, headers = setup_summary
    for i in range(52):
        reservation = spend.reserve(engine, "model-a", 100)
        spend.settle(engine, reservation, i, input_tokens=i + 1, cached_tokens=1, output_tokens=2)
    spend.reserve(engine, "model-b", 500)
    with engine.connect() as connection:
        before = connection.execute(select(spend.ledger).order_by(spend.ledger.c.id)).all()
    data = client.get("/spend/summary", headers=headers).json()
    assert data["totals"] == {"reserved_microdollars": 500, "settled_microdollars": sum(range(52))}
    assert data["per_model"] == [
        {"model": "model-a", "reserved_microdollars": 0, "settled_microdollars": sum(range(52))},
        {"model": "model-b", "reserved_microdollars": 500, "settled_microdollars": 0},
    ]
    assert len(data["recent_entries"]) == 50
    assert data["recent_entries"][0] == {
        "model": "model-a", "input_tokens": 52, "cached_tokens": 1,
        "output_tokens": 2, "cost_microdollars": 51,
    }
    assert data["recent_entries"][-1]["cost_microdollars"] == 2
    with engine.connect() as connection:
        assert connection.execute(select(spend.ledger).order_by(spend.ledger.c.id)).all() == before
