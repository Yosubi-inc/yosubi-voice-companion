import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import get_db
from app.guidance import healthcare_guidance
from app.main import app
from app.models import Base, CommunityResource


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'guidance.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(CommunityResource(category="food", name_en="Local pantry", name_es="Despensa local", location="Example town"))
        db.commit()
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize("lang,disclaimer", [("en", "Consult a qualified healthcare professional"), ("es", "Consulte a un profesional de salud")])
def test_healthcare_navigation(client, lang, disclaimer):
    response = client.get("/guidance/healthcare", params={"lang": lang})
    assert response.status_code == 200
    body = response.json()
    assert disclaimer in body["disclaimer"]
    assert all(body[key] for key in ("checklist", "what_to_bring", "questions"))
    assert body == healthcare_guidance(lang)
    content = str(body).lower()
    assert not any(term in content for term in ("you have diabetes", "take this medicine", "tiene diabetes", "tome este medicamento"))


@pytest.mark.parametrize("lang,word", [("en", "office"), ("es", "dirección")])
def test_government_visit(client, lang, word):
    body = client.get("/guidance/government", params={"lang": lang}).json()
    assert body["benefit_lookup"] and word in " ".join(body["office_visit"]).lower()


@pytest.mark.parametrize("lang,word", [("en", "due"), ("es", "pago")])
def test_utility_help(client, lang, word):
    body = client.get("/guidance/utilities", params={"lang": lang}).json()
    assert word in " ".join(body["bill_reading"]).lower()
    assert body["payment_options"] and body["hardship_programs"]


@pytest.mark.parametrize("lang,name", [("en", "Local pantry"), ("es", "Despensa local")])
def test_community_directory(client, lang, name):
    entries = client.get("/guidance/community", params={"lang": lang}).json()
    assert {"food", "housing", "transportation"} <= {row["category"] for row in entries}
    filtered = client.get("/guidance/community", params={"lang": lang, "category": "food"}).json()
    assert all(row["category"] == "food" for row in filtered)
    assert any(row["name"] == name and not row["example"] for row in filtered)
    assert client.get("/guidance/community", params={"lang": lang, "category": "missing"}).json() == []


def test_invalid_language_rejected(client):
    for path in ("healthcare", "government", "utilities", "community"):
        assert client.get(f"/guidance/{path}", params={"lang": "fr"}).status_code == 422
