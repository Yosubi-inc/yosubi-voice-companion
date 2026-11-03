import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base, Incident
from app.safety import authorize
from fastapi import HTTPException


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as api:
        yield api, engine
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize("language,text", [
    ("en", "A caller claiming to be Medicare demands immediate payment and asks for a verification code."),
    ("es", "Una llamada dice ser de Medicare y exige pago inmediato y pide un código de verificación."),
])
def test_medicare_scam(client, language, text):
    data = client[0].post('/safety/assess', json={'text': text, 'language': language}).json()
    assert data['suspicious'] and 'verification_code' in data['signals']
    assert data['escalation']['trusted_contact_offered']
    guidance = ' '.join(data['guidance']).lower()
    assert all(word in guidance for word in (('do not', 'independently', "never the caller") if language == 'en' else ('no pague', 'por su cuenta', 'nunca el número')))


@pytest.mark.parametrize('text', [
    'I bought a gift card for my granddaughter for her birthday.',
    'My bank mailed me a new debit card and I will visit the branch next week.',
])
def test_legitimate_requests(client, text):
    assert client[0].post('/safety/assess', json={'text': text}).json()['suspicious'] is False


def test_emergency(client):
    result = client[0].post('/safety/assess', json={'text': 'I have chest pain', 'language': 'es'}).json()
    assert result['emergency'] and result['escalation']['emergency_services']
    assert 'emergencia' in result['guidance'][0]


def test_consent_grants_revocation_and_hard_refusals(client):
    api, engine = client
    path = '/safety/profiles/p'
    assert api.put('/profiles/p/consent', json={'granted': True}).status_code == 200
    assert api.post(path + '/contacts', json={'name': 'Ana', 'consent': False}).status_code == 403
    contact = api.post(path + '/contacts', json={'name': 'Ana', 'consent': True}).json()['id']
    assert api.post(path + '/incidents', json={'summary': 'Call', 'consent': False}).status_code == 403
    assert api.post(path + '/incidents', json={'summary': 'Call', 'consent': True, 'contact_id': contact}).status_code == 403
    grant = api.post(path + f'/contacts/{contact}/grants', json={'permission': 'save_incident', 'consent': True}).json()['id']
    assert api.post(path + '/escalation', json={'consent': True, 'contact_id': contact}).status_code == 403
    assert api.post(path + '/incidents', json={'summary': 'Call', 'consent': True, 'contact_id': contact}).status_code == 200
    assert api.post(path + f'/grants/{grant}/revoke', json={'consent': True}).status_code == 200
    assert api.post(path + '/incidents', json={'summary': 'Another', 'consent': True, 'contact_id': contact}).status_code == 403
    with Session(engine) as db:
        assert len(db.scalars(select(Incident)).all()) == 1
        for action in ('payment', 'purchase', 'account_change', 'share_protected_info'):
            with pytest.raises(HTTPException):
                authorize(db, 'p', action, True, contact)
    assert api.delete('/profiles/p').status_code == 200
    with Session(engine) as db:
        assert db.scalars(select(Incident)).all() == []
