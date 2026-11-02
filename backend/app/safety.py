"""Local safety guidance and consent-gated trusted-circle operations.

These endpoints do not authenticate callers or contact people. Deployments must put
identity verification in front of them before exposing profile data or operations.
"""
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Consent, Grant, Incident, Profile, TrustedContact

router = APIRouter(prefix="/safety", tags=["safety"])
Permission = Literal["receive_escalation", "save_incident"]


def deny(en: str, es: str):
    raise HTTPException(status_code=403, detail={"en": en, "es": es})


def consent_required(db: Session, profile_id: str, consent: bool):
    record = db.get(Consent, profile_id)
    if not consent or record is None or not record.granted:
        deny("Explicit consent is required.", "Se requiere consentimiento explícito.")


def authorize(db: Session, profile_id: str, action: str, consent: bool, contact_id: int | None = None):
    # This denylist applies even if a malformed or legacy grant exists.
    if action not in ("receive_escalation", "save_incident", "manage_circle"):
        deny("This action is not allowed.", "Esta acción no está permitida.")
    consent_required(db, profile_id, consent)
    if contact_id is not None:
        contact = db.get(TrustedContact, contact_id)
        if contact is None or contact.profile_id != profile_id or action == "manage_circle":
            deny("This contact does not have permission.", "Este contacto no tiene permiso.")
        grant = db.scalar(select(Grant).where(Grant.contact_id == contact_id,
                                               Grant.permission == action,
                                               Grant.revoked.is_(False)))
        if grant is None:
            deny("This contact does not have permission.", "Este contacto no tiene permiso.")


class Assessment(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    language: Literal["en", "es"] = "en"


# Require a request context plus a warning sign, avoiding labels based on unusual
# payment methods or a named institution alone.
PATTERNS = {
    "impersonation": r"\b(medicare|social security|seguro social|bank|banco|utility|electric company|compañ[ií]a de luz|familia|family|grandson|granddaughter|niet[oa])\b",
    "urgency": r"\b(immediate(?:ly)?|right now|urgent(?:ly)?|at once|today|ahora mismo|inmediat[oa](?:mente)?|urgente|de inmediato|hoy mismo)\b",
    "secrecy": r"\b(secret|don.t tell|keep (?:this|it) (?:a )?secret|secreto|no (?:le )?digas|no (?:le )?diga|no cuentes)\b",
    "unusual_payment": r"\b(gift cards?|crypto(?:currency)?|bitcoin|wire transfer|tarjetas? de regalo|criptomonedas?|transferencia bancaria)\b",
    "verification_code": r"\b(verification code|one.time (?:code|password)|otp|password|c[oó]digo de verificaci[oó]n|c[oó]digo de seguridad|contraseñ[aá])\b",
    "request": r"\b(asks?|asking|demands?|demanding|wants?|told|caller|called|call|message|email|pay|payment|send|give|share|pide|pidi[oó]|exige|exigi[oó]|llam(?:a|ada|aron|ó)|mensaje|correo|pagar|pago|enviar|dar|compartir)\b",
}
EMERGENCY = re.compile(r"\b(can.t breathe|cannot breathe|not breathing|chest pain|stroke|unconscious|severe bleeding|suicid(?:e|al)|kill myself|no puedo respirar|no respira|dolor de pecho|derrame cerebral|inconsciente|sangrado abundante|suicid(?:io|arme))\b", re.I)


def assess(text: str, language: str) -> dict:
    found = {key for key, pattern in PATTERNS.items() if re.search(pattern, text, re.I)}
    risk = "request" in found and bool(found & {"urgency", "secrecy", "unusual_payment", "verification_code"})
    emergency = bool(EMERGENCY.search(text))
    guidance = []
    if emergency:
        guidance.append({"en": "This may be an emergency. Call emergency services now or ask a trusted contact to help you call.", "es": "Esto puede ser una emergencia. Llame ahora a los servicios de emergencia o pida ayuda a un contacto de confianza para llamar."}[language])
    if risk:
        guidance.append({"en": "This request has warning signs and may be a scam. Do not pay or share passwords, verification codes, or financial details. Contact the organization using a number you found independently, such as on its official website or your statement, never the caller's number. You can ask an approved trusted contact for help.", "es": "Esta solicitud tiene señales de alerta y podría ser una estafa. No pague ni comparta contraseñas, códigos de verificación ni datos financieros. Comuníquese con la organización usando un número que haya encontrado por su cuenta, por ejemplo en su sitio oficial o estado de cuenta, nunca el número que le dio quien llamó. Puede pedir ayuda a un contacto de confianza aprobado."}[language])
    if not guidance:
        guidance.append({"en": "I do not see these warning signs. Take your time and verify any request if unsure.", "es": "No veo estas señales de alerta. Tómese su tiempo y verifique cualquier solicitud si tiene dudas."}[language])
    return {"suspicious": risk, "emergency": emergency,
            "signals": sorted(found - {"request"}) if risk else [], "guidance": guidance,
            "escalation": {"emergency_services": emergency, "trusted_contact_offered": emergency or risk}}


@router.post("/assess")
def assess_request(data: Assessment):
    return assess(data.text, data.language)


class ConsentAction(BaseModel):
    consent: StrictBool
    contact_id: int | None = None


class ContactInput(ConsentAction):
    name: str = Field(min_length=1, max_length=200)


class GrantInput(ConsentAction):
    permission: Permission


class IncidentInput(ConsentAction):
    summary: str = Field(min_length=1, max_length=5000)


@router.post("/profiles/{profile_id}/contacts")
def create_contact(profile_id: str, data: ContactInput, db: Session = Depends(get_db)):
    authorize(db, profile_id, "manage_circle", data.consent, data.contact_id)
    contact = TrustedContact(profile_id=profile_id, name=data.name)
    db.add(contact)
    db.commit()
    return {"id": contact.id}


@router.post("/profiles/{profile_id}/contacts/{contact_id}/grants")
def create_grant(profile_id: str, contact_id: int, data: GrantInput, db: Session = Depends(get_db)):
    authorize(db, profile_id, "manage_circle", data.consent, data.contact_id)
    contact = db.get(TrustedContact, contact_id)
    if contact is None or contact.profile_id != profile_id:
        raise HTTPException(404, detail={"en": "Contact not found.", "es": "Contacto no encontrado."})
    grant = Grant(contact_id=contact_id, permission=data.permission, revoked=False)
    db.add(grant)
    db.commit()
    return {"id": grant.id}


@router.post("/profiles/{profile_id}/grants/{grant_id}/revoke")
def revoke_grant(profile_id: str, grant_id: int, data: ConsentAction, db: Session = Depends(get_db)):
    authorize(db, profile_id, "manage_circle", data.consent, data.contact_id)
    grant = db.get(Grant, grant_id)
    contact = db.get(TrustedContact, grant.contact_id) if grant else None
    if contact is None or contact.profile_id != profile_id:
        raise HTTPException(404, detail={"en": "Grant not found.", "es": "Permiso no encontrado."})
    grant.revoked = True
    db.commit()
    return {"revoked": True}


@router.post("/profiles/{profile_id}/incidents")
def save_incident(profile_id: str, data: IncidentInput, db: Session = Depends(get_db)):
    authorize(db, profile_id, "save_incident", data.consent, data.contact_id)
    incident = Incident(profile_id=profile_id, summary=data.summary)
    db.add(incident)
    db.commit()
    return {"id": incident.id}


@router.post("/profiles/{profile_id}/escalation")
def escalation(profile_id: str, data: ConsentAction, db: Session = Depends(get_db)):
    authorize(db, profile_id, "receive_escalation", data.consent, data.contact_id)
    return {"en": "Please contact your approved trusted person directly.", "es": "Comuníquese directamente con su contacto de confianza aprobado."}
