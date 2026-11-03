"""Batch speech transcription with a prepaid spend reservation."""
import io
import math
import os
import struct
import wave

from mutagen.mp3 import MP3
import httpx
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app import spend
from app.database import get_engine

MODEL = "muse-voice-transcribe-1.0"
MAX_BYTES = 10_000_000
FORMATS = {"audio/wav": ("wav", {"wav"}), "audio/webm": ("webm", {"matroska", "webm"}),
           "audio/mpeg": ("mp3", {"mp3"})}
BAD_AUDIO = {"en": "Please provide a valid WAV, WebM, or MP3 audio file.", "es": "Proporcione un archivo de audio WAV, WebM o MP3 válido."}
TOO_LARGE = {"en": "Audio must be 10 MB or smaller.", "es": "El audio debe ser de 10 MB o menos."}
LIMIT = {"en": "The assistant spending limit has been reached.", "es": "Se ha alcanzado el límite de gasto del asistente."}
UNAVAILABLE = {"en": "Transcription is unavailable right now.", "es": "La transcripción no está disponible en este momento."}


def _elements(data, start, end):
    """Read bounded EBML elements, including unknown-size WebM segments."""
    pos = start
    while pos < end:
        first = data[pos]
        if not first:
            raise ValueError("invalid EBML")
        width = 9 - first.bit_length()
        if width > 4 or pos + width >= end:
            raise ValueError("invalid EBML id")
        element = int.from_bytes(data[pos:pos + width], "big")
        pos += width
        first = data[pos]
        if not first:
            raise ValueError("invalid EBML size")
        width = 9 - first.bit_length()
        if width > 8 or pos + width > end:
            raise ValueError("invalid EBML size")
        size = int.from_bytes(data[pos:pos + width], "big") & ((1 << (7 * width)) - 1)
        pos += width
        stop = end if size == (1 << (7 * width)) - 1 else pos + size
        if stop > end:
            raise ValueError("truncated EBML")
        yield element, pos, stop
        pos = stop


def _webm_duration(data):
    roots = list(_elements(data, 0, len(data)))
    if not roots or roots[0][0] != 0x1A45DFA3:
        raise ValueError("missing EBML header")
    header = list(_elements(data, roots[0][1], roots[0][2]))
    if not any(e == 0x4282 and data[a:b] == b"webm" for e, a, b in header):
        raise ValueError("not WebM")
    segments = [(a, b) for e, a, b in roots if e == 0x18538067]
    if len(segments) != 1:
        raise ValueError("missing segment")
    children = list(_elements(data, *segments[0]))
    scale, duration, tracks = 1_000_000, None, []
    clusters = []
    for element, start, end in children:
        if element == 0x1549A966:
            for key, a, b in _elements(data, start, end):
                if key == 0x2AD7B1:
                    scale = int.from_bytes(data[a:b], "big")
                elif key == 0x4489:
                    if b - a not in (4, 8):
                        raise ValueError("invalid duration")
                    duration = struct.unpack(">f" if b - a == 4 else ">d", data[a:b])[0]
        elif element == 0x1654AE6B:
            for key, a, b in _elements(data, start, end):
                if key == 0xAE:
                    fields = {k: data[x:y] for k, x, y in _elements(data, a, b)}
                    if int.from_bytes(fields.get(0x83, b""), "big") == 2:
                        tracks.append((int.from_bytes(fields.get(0xD7, b""), "big"), fields.get(0x86)))
        elif element == 0x1F43B675:
            clusters.append((start, end))
    if len(tracks) != 1 or not scale:
        raise ValueError("invalid audio tracks")
    if duration is not None:
        return duration * scale / 1_000_000_000
    # Browser MediaRecorder commonly omits Duration. Use the last Opus block
    # timestamp plus its packet duration, without trusting a client parameter.
    track, codec = tracks[0]
    if codec != b"A_OPUS" or not 0 < track < 127:
        raise ValueError("missing duration")
    last = None
    for start, end in clusters:
        timestamp = 0
        for key, a, b in _elements(data, start, end):
            if key == 0xE7:
                timestamp = int.from_bytes(data[a:b], "big")
            elif key == 0xA3 and b - a >= 5 and data[a] == 0x80 | track:
                if data[a + 3] & 0x06:
                    raise ValueError("laced audio unsupported")
                relative = int.from_bytes(data[a + 1:a + 3], "big", signed=True)
                toc = data[a + 4]
                config, code = toc >> 3, toc & 3
                frame_ms = (2.5 * (2 ** (config & 3)) if config >= 16 else
                            10 * (2 ** (config & 1)) if config >= 12 else
                            (10, 20, 40, 60)[config & 3])
                count = 1 if code == 0 else 2 if code in (1, 2) else (data[a + 5] & 63 if b - a >= 6 else 0)
                packet_ms = frame_ms * count
                if not 0 < packet_ms <= 120:
                    raise ValueError("invalid Opus packet")
                end_time = (timestamp + relative) * scale / 1_000_000_000 + packet_ms / 1000
                last = max(last or 0, end_time)
    if last is None:
        raise ValueError("missing audio blocks")
    return last


def audio_duration(data, formats):
    """Probe audio locally, without trusting a client-provided duration."""
    try:
        if "wav" in formats:
            with wave.open(io.BytesIO(data), "rb") as wav:
                frames, rate = wav.getnframes(), wav.getframerate()
                if not rate or len(wav.readframes(frames)) != frames * wav.getnchannels() * wav.getsampwidth():
                    raise ValueError("truncated WAV")
                duration = frames / rate
        elif "mp3" in formats:
            duration = MP3(io.BytesIO(data)).info.length
        elif "webm" in formats:
            duration = _webm_duration(data)
        else:
            raise ValueError("unsupported format")
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("invalid duration")
        if duration * 50 > spend.CAP:
            raise HTTPException(429, detail=LIMIT)
        return duration
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, detail=BAD_AUDIO) from None


def transcribe(data, content_type, language):
    key = os.getenv("MODEL_API_KEY")
    if not key:
        raise HTTPException(503, detail=UNAVAILABLE)
    extension, formats = FORMATS[content_type]
    duration = audio_duration(data, formats)
    # $0.18/hour = 50 microdollars per second. Round up before reserving.
    cost = math.ceil(duration * 50)
    try:
        reservation = spend.reserve(get_engine(), MODEL, cost)
    except spend.SpendLimitExceeded:
        raise HTTPException(429, detail=LIMIT) from None
    try:
        # Meta's IPv6 edge does not serve the model API (404); pin outbound to IPv4.
        with httpx.Client(timeout=60, transport=httpx.HTTPTransport(local_address="0.0.0.0")) as client:
            response = client.post(os.getenv("META_BASE_URL", "https://api.meta.ai/v1").rstrip("/") + "/audio/transcriptions",
                                   headers={"Authorization": f"Bearer {key}"},
                                   data={"model": MODEL, "language": language, "response_format": "verbose_json"},
                                   files={"file": ("audio." + extension, data, content_type)})
            response.raise_for_status()
            result = response.json()
        transcript, detected = result["text"], result["language"]
        if not isinstance(transcript, str) or not isinstance(detected, str) or not detected:
            raise ValueError("invalid transcription")
        spend.settle(get_engine(), reservation, cost, input_tokens=0, cached_tokens=0, output_tokens=0)
        return {"transcript": transcript, "language": detected, "duration": float(duration)}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        # Unknown outcomes retain their reservation for reconciliation.
        raise HTTPException(503, detail=UNAVAILABLE) from None


async def stt_endpoint(request: Request, language: str = "en"):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in FORMATS:
        raise HTTPException(415, detail=BAD_AUDIO)
    if language not in ("en", "es"):
        raise HTTPException(400, detail={"en": "Language must be en or es.", "es": "El idioma debe ser en o es."})
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, detail=TOO_LARGE)
        data.extend(chunk)
    return await run_in_threadpool(transcribe, bytes(data), content_type, language)
