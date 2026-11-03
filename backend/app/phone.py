"""Twilio voice webhooks and a swappable outbound call provider."""
import base64
import hashlib
import hmac
import os
import re
from typing import Protocol
from urllib.parse import parse_qsl
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Reminder, Task
from app.resilience import retry

router = APIRouter(prefix="/phone")


def public_url(request: Request) -> str:
    base = os.environ.get("PHONE_WEBHOOK_BASE_URL", "").rstrip("/")
    if not base:
        raise HTTPException(503, detail="Phone webhook configuration unavailable / Configuración telefónica no disponible")
    return base + request.url.path + ("?" + request.url.query if request.url.query else "")


async def validated_form(request: Request) -> dict[str, str]:
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not token:
        raise HTTPException(503, detail="Phone authentication unavailable / Autenticación telefónica no disponible")
    pairs = parse_qsl((await request.body()).decode("utf-8"), keep_blank_values=True)
    # Twilio signs each distinct value of each parameter in sorted order.
    payload = public_url(request) + "".join(k + v for k in sorted({k for k, _ in pairs}) for v in sorted({v for key, v in pairs if key == k}))
    expected = base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    if not hmac.compare_digest(expected, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, detail="Invalid signature / Firma inválida")
    return dict(pairs)


def language(text: str, previous: str) -> str:
    text = text.lower()
    if re.search(r'\b(english|inglés|ingles)\b', text):
        return "en"
    if re.search(r'\b(spanish|español|espanol)\b', text) or re.search(r'[¿¡áéíóúñ]|\b(hola|gracias|quiero|puedes|necesito|si|por favor|recordatorio|tarea)\b', text):
        return "es"
    if re.search(r'\b(hello|hi|thanks|please|can you|i want|reminder|task|yes)\b', text):
        return "en"
    return previous


def say(parent, text: str, lang: str):
    ET.SubElement(parent, "Say", {"language": "es-US" if lang == "es" else "en-US", "voice": "Polly.Mia" if lang == "es" else "Polly.Joanna"}).text = text


def xml(root):
    return Response(ET.tostring(root, encoding="unicode"), media_type="application/xml")


def gather(root, lang: str, prompt: str):
    node = ET.SubElement(root, "Gather", {"input": "speech", "action": f"/phone/turn?lang={lang}", "method": "POST", "language": "es-US" if lang == "es" else "en-US", "speechTimeout": "auto"})
    say(node, prompt, lang)
    say(root, "No escuché nada. Adiós." if lang == "es" else "I did not hear anything. Goodbye.", lang)
    ET.SubElement(root, "Hangup")


@router.post("/inbound")
async def inbound(request: Request, form: dict = Depends(validated_form)):
    lang = "es" if request.query_params.get("lang") == "es" else "en"
    root = ET.Element("Response")
    gather(root, lang, "Hola. ¿En qué puedo ayudarte?" if lang == "es" else "Hello. How can I help you?")
    return xml(root)


@router.post("/turn")
async def turn(request: Request, form: dict = Depends(validated_form)):
    lang = language(form.get("SpeechResult", ""), "es" if request.query_params.get("lang") == "es" else "en")
    text = form.get("SpeechResult", "").strip()
    root = ET.Element("Response")
    if re.search(r'\b(goodbye|bye|adiós|adios)\b', text, re.I):
        say(root, "Adiós." if lang == "es" else "Goodbye.", lang)
        ET.SubElement(root, "Hangup")
    else:
        if re.search(r'demo action|acci[oó]n de prueba', text, re.I):
            reply = "Entendido. Acción de prueba completada. No se cambió nada fuera de esta demostración." if lang == "es" else "Understood. Demo action completed. Nothing outside this demonstration was changed."
        else:
            reply = "Te escucho. ¿En qué puedo ayudarte?" if lang == "es" else "I am listening. How can I help?"
        gather(root, lang, reply)
    return xml(root)


@router.post("/reminder/{reminder_id}")
async def reminder_call(reminder_id: int, request: Request, form: dict = Depends(validated_form), db: Session = Depends(get_db)):
    reminder = db.get(Reminder, reminder_id)
    task = db.get(Task, reminder.task_id) if reminder else None
    if not task:
        raise HTTPException(404, detail="Reminder not found / Recordatorio no encontrado")
    lang = "es" if request.query_params.get("lang") == "es" else "en"
    root = ET.Element("Response")
    say(root, ("Recordatorio: " if lang == "es" else "Reminder: ") + task.title, lang)
    say(root, "Adiós." if lang == "es" else "Goodbye.", lang)
    ET.SubElement(root, "Hangup")
    return xml(root)


@router.post("/status")
async def status(form: dict = Depends(validated_form)):
    return Response(status_code=204)


class CallProvider(Protocol):
    def place_call(self, *, to: str, from_: str, url: str, status_callback: str) -> str: ...


class TwilioProvider:
    def __init__(self, client):
        self.client = client

    def place_call(self, *, to: str, from_: str, url: str, status_callback: str) -> str:
        # A timeout or server error can mean a call was accepted. Only a 429
        # confirms rejection and is safe to retry without duplicating a call.
        call = retry(lambda: self.client.calls.create(to=to, from_=from_, url=url, method="POST", status_callback=status_callback, status_callback_method="POST"), retryable=lambda exc: getattr(exc, "status", None) == 429 or getattr(exc, "status_code", None) == 429)
        return call.sid


def reminder_delivery(provider: CallProvider, *, to: str, from_: str, base_url: str, lang: str = "en"):
    def deliver(reminder: Reminder) -> str:
        sid = provider.place_call(to=to, from_=from_, url=f"{base_url.rstrip('/')}/phone/reminder/{reminder.id}?lang={lang}", status_callback=f"{base_url.rstrip('/')}/phone/status")
        if not sid:
            raise ValueError("No call request identifier")
        return "Call request accepted: " + sid
    return deliver


def configured_delivery():
    from app.scheduler import unavailable
    keys = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "PHONE_TEST_DESTINATION", "PHONE_WEBHOOK_BASE_URL")
    values = [os.environ.get(key) for key in keys]
    if os.environ.get("PHONE_TEST_MODE") != "1" or not all(values):
        return unavailable
    from twilio.rest import Client
    sid, token, from_, to, base = values
    return reminder_delivery(TwilioProvider(Client(sid, token)), to=to, from_=from_, base_url=base, lang="es" if os.environ.get("PHONE_LANGUAGE") == "es" else "en")
