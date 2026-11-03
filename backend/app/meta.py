"""Injection seam for a future Meta client; no model calls are made here."""
import os

from fastapi import HTTPException

from app.resilience import retry


def model_call(call):
    if not os.getenv("MODEL_API_KEY"):
        raise HTTPException(503, detail={"en": "The assistant is unavailable right now.", "es": "El asistente no está disponible en este momento."})
    return retry(call)
