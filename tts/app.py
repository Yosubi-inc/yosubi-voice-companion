"""Self-hosted Meta MMS voice: text in, WAV out. No external calls."""
import hashlib
import hmac
import io
import os
import wave

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from transformers import VitsModel, VitsTokenizer

CHECKPOINTS = {"en": "facebook/mms-tts-eng", "spa": "facebook/mms-tts-spa"}
CACHE_SIZE = 200

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["POST"], allow_headers=["*"])
_models = {}
_cache = {}


class SpeakInput(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: str = Field(default="en", pattern="^(en|es)$")


def model_for(language):
    key = "spa" if language == "es" else "en"
    if key not in _models:
        checkpoint = CHECKPOINTS[key]
        _models[key] = (VitsTokenizer.from_pretrained(checkpoint), VitsModel.from_pretrained(checkpoint))
    return _models[key]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tts")
def speak(body: SpeakInput, request: Request):
    token = os.getenv("DEMO_API_TOKEN")
    if token:
        scheme, separator, credential = request.headers.get("authorization", "").partition(" ")
        if not separator or scheme.lower() != "bearer" or not hmac.compare_digest(credential.encode(), token.encode()):
            raise HTTPException(401)
    digest = hashlib.sha256((body.language + "\x00" + body.text).encode("utf-8")).hexdigest()
    if digest in _cache:
        return Response(content=_cache[digest], media_type="audio/wav")
    try:
        tokenizer, model = model_for(body.language)
        inputs = tokenizer(body.text, return_tensors="pt")
        with torch.no_grad():
            waveform = model(**inputs).waveform[0]
        pcm = (waveform.numpy() * 32767).astype("int16").tobytes()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(pcm)
        data = buffer.getvalue()
    except Exception:
        raise HTTPException(503) from None
    if len(_cache) >= CACHE_SIZE:
        _cache.pop(next(iter(_cache)))
    _cache[digest] = data
    return Response(content=data, media_type="audio/wav")
