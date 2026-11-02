from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, StrictBool, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Consent, Grant, Incident, Preference, Profile, TrustedContact
from sqlalchemy import delete, select

app = FastAPI(title="Yosubi Voice Companion")

FIELDS = ("name", "preferred_language", "communication_needs")
# Drafts are conversation-only and are never written to the database before consent.
drafts: dict[str, dict] = {}


class Answer(BaseModel):
    field: str
    value: str = Field(min_length=1, max_length=2000)

    @field_validator("value")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank / El valor no puede estar vacío")
        return value


class ConsentInput(BaseModel):
    granted: StrictBool


def error(status: int, en: str, es: str):
    raise HTTPException(status_code=status, detail={"en": en, "es": es})


def saved_values(db: Session, profile_id: str) -> dict:
    profile = db.get(Profile, profile_id)
    preference = db.get(Preference, profile_id)
    return {
        "name": profile.name if profile else None,
        "preferred_language": preference.preferred_language if preference else None,
        "communication_needs": preference.communication_needs if preference else None,
    }


def get_draft(session_id: str) -> dict:
    draft = drafts.get(session_id)
    if draft is None:
        error(404, "Conversation not found", "Conversación no encontrada")
    return draft


def state(draft: dict) -> dict:
    values = draft["values"]
    return {"session_id": draft["session_id"], "values": values.copy(),
            "next_field": next((field for field in FIELDS if not values[field]), None)}


def validate_answer(answer: Answer):
    if answer.field not in FIELDS:
        error(422, "Unknown field", "Campo desconocido")
    if answer.field == "preferred_language" and answer.value not in ("en", "es"):
        error(422, "Language must be en or es", "El idioma debe ser en o es")
    if answer.field == "name" and len(answer.value) > 200:
        error(422, "Name is too long", "El nombre es demasiado largo")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/profiles/{profile_id}/conversations")
def start_conversation(profile_id: str, db: Session = Depends(get_db)):
    session_id = str(uuid4())
    draft = {"session_id": session_id, "profile_id": profile_id,
             "values": saved_values(db, profile_id), "changed": set()}
    drafts[session_id] = draft
    return state(draft)


@app.put("/conversations/{session_id}/answer")
def answer(session_id: str, answer: Answer):
    draft = get_draft(session_id)
    validate_answer(answer)
    if answer.field != state(draft)["next_field"]:
        error(409, "Answer the next field first", "Responda primero el siguiente campo")
    draft["values"][answer.field] = answer.value
    draft["changed"].add(answer.field)
    return state(draft)


@app.put("/profiles/{profile_id}/consent")
def record_consent(profile_id: str, consent: ConsentInput, db: Session = Depends(get_db)):
    profile = db.get(Profile, profile_id)
    if profile is None:
        profile = Profile(id=profile_id)
        db.add(profile)
        db.flush()
    record = db.get(Consent, profile_id)
    if record is None:
        record = Consent(profile_id=profile_id, granted=consent.granted)
        db.add(record)
    else:
        record.granted = consent.granted
    db.commit()
    return {"granted": consent.granted}


def require_consent(db: Session, profile_id: str):
    consent = db.get(Consent, profile_id)
    if consent is None or not consent.granted:
        error(403, "Explicit consent is required to save", "Se requiere consentimiento explícito para guardar")


@app.post("/conversations/{session_id}/save")
def save(session_id: str, db: Session = Depends(get_db)):
    draft = get_draft(session_id)
    profile_id = draft["profile_id"]
    require_consent(db, profile_id)
    profile = db.get(Profile, profile_id)
    preference = db.get(Preference, profile_id)
    if preference is None:
        preference = Preference(profile_id=profile_id)
        db.add(preference)
    values = draft["values"]
    if "name" in draft["changed"]:
        profile.name = values["name"]
    for field in ("preferred_language", "communication_needs"):
        if field in draft["changed"]:
            setattr(preference, field, values[field])
    db.commit()
    draft["changed"].clear()
    return saved_values(db, profile_id)


@app.get("/profiles/{profile_id}")
def review(profile_id: str, db: Session = Depends(get_db)):
    if db.get(Profile, profile_id) is None:
        error(404, "Profile not found", "Perfil no encontrado")
    return saved_values(db, profile_id)


@app.patch("/profiles/{profile_id}")
def correct(profile_id: str, answer: Answer, db: Session = Depends(get_db)):
    validate_answer(answer)
    require_consent(db, profile_id)
    profile = db.get(Profile, profile_id)
    preference = db.get(Preference, profile_id)
    if answer.field == "name":
        profile.name = answer.value
    else:
        if preference is None:
            preference = Preference(profile_id=profile_id)
            db.add(preference)
        setattr(preference, answer.field, answer.value)
    db.commit()
    # Keep active conversations from restoring stale values on their next save.
    for draft in drafts.values():
        if draft["profile_id"] == profile_id:
            draft["values"][answer.field] = answer.value
            draft["changed"].discard(answer.field)
    return saved_values(db, profile_id)


@app.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    # Explicit deletes also work with SQLite when foreign keys are disabled.
    contact_ids = select(TrustedContact.id).where(TrustedContact.profile_id == profile_id)
    db.execute(delete(Grant).where(Grant.contact_id.in_(contact_ids)))
    db.execute(delete(TrustedContact).where(TrustedContact.profile_id == profile_id))
    db.execute(delete(Incident).where(Incident.profile_id == profile_id))
    for model in (Preference, Consent, Profile):
        row = db.get(model, profile_id)
        if row is not None:
            db.delete(row)
            db.flush()
    db.commit()
    for session_id in [key for key, draft in drafts.items() if draft["profile_id"] == profile_id]:
        del drafts[session_id]
    return {"deleted": True}

from app.tasks import router as tasks_router
app.include_router(tasks_router)

from app.safety import router as safety_router
app.include_router(safety_router)
