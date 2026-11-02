import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app, drafts
from app.models import Base, Consent, Preference, Profile


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    drafts.clear()
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()
    drafts.clear()
    engine.dispose()


def test_gradual_onboarding_consent_review_correction_and_persistence(client):
    api, engine = client
    start = api.post("/profiles/person-1/conversations").json()
    session = start["session_id"]
    assert start["next_field"] == "name"
    assert api.put(f"/conversations/{session}/answer", json={"field": "preferred_language", "value": "es"}).status_code == 409
    for field, value, next_field in [("name", "Ana", "preferred_language"),
                                     ("preferred_language", "es", "communication_needs"),
                                     ("communication_needs", "Hablar despacio", None)]:
        response = api.put(f"/conversations/{session}/answer", json={"field": field, "value": value})
        assert response.status_code == 200
        assert response.json()["next_field"] == next_field
    assert api.post(f"/conversations/{session}/save").status_code == 403
    assert api.patch("/profiles/person-1", json={"field": "name", "value": "A"}).status_code == 403
    with Session(engine) as db:
        assert db.scalars(select(Profile)).all() == []
        assert db.scalars(select(Preference)).all() == []
    assert api.put("/profiles/person-1/consent", json={"granted": True}).status_code == 200
    expected = {"name": "Ana", "preferred_language": "es", "communication_needs": "Hablar despacio"}
    assert api.post(f"/conversations/{session}/save").json() == expected
    assert api.get("/profiles/person-1").json() == expected
    expected["name"] = "Anita"
    assert api.patch("/profiles/person-1", json={"field": "name", "value": "Anita"}).json() == expected
    new_session = api.post("/profiles/person-1/conversations").json()
    assert new_session["values"] == expected
    assert new_session["next_field"] is None
    assert api.put("/profiles/person-1/consent", json={"granted": False}).status_code == 200
    assert api.post(f"/conversations/{session}/save").status_code == 403
    assert api.patch("/profiles/person-1", json={"field": "name", "value": "Ana"}).status_code == 403
    assert api.delete("/profiles/person-1").json() == {"deleted": True}
    with Session(engine) as db:
        for model in (Profile, Preference, Consent):
            assert db.scalars(select(model)).all() == []
    assert api.get("/profiles/person-1").status_code == 404
    assert api.post(f"/conversations/{session}/save").status_code == 404
