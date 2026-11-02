from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.main import app
from app.models import Base


def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_schema_can_be_created():
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        assert set(inspect(engine).get_table_names()) == {
            "profiles", "preferences", "consents", "tasks", "reminders",
            "action_log", "trusted_contacts", "grants", "incidents",
            "spend_ledger", "audit_records",
        }
    finally:
        engine.dispose()
