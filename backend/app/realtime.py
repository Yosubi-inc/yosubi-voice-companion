"""Live transcription relay: browser streams PCM, Meta streams transcripts back."""
import asyncio
import hmac
import json
import math
import os
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import get_engine
from app import spend

router = APIRouter()

MODEL = "muse-voice-transcribe-1.0"
MAX_SESSION_SECONDS = 300
MAX_FRAME_BYTES = 1_000_000
SESSION_RESERVE_MICRODOLLARS = 30_000  # 600 s of audio at $0.18/hr.


def meta_realtime_url():
    base = os.getenv("META_BASE_URL", "https://api.meta.ai/v1").rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return base + "/asr/realtime?sessionId=" + uuid4().hex


def handshake(key, language):
    return {
        "authorization": {"accessToken": "Bearer " + key},
        "audioEncoding": "PCM_16KHZ",
        "model": MODEL,
        "mode": "ENDPOINTING",
        "languageBias": ["Spanish" if language == "es" else "English"],
    }


@router.websocket("/voice/stream")
async def voice_stream(client: WebSocket, token: str = "", language: str = "en"):
    expected = os.getenv("DEMO_API_TOKEN")
    if language not in ("en", "es"):
        await client.close(code=4400, reason="language")
        return
    await client.accept()
    if expected and not hmac.compare_digest(token.encode(), expected.encode()):
        await client.close(code=4401, reason="auth")
        return
    key = os.getenv("MODEL_API_KEY")
    if not key:
        await client.close(code=4503, reason="unavailable")
        return
    try:
        reservation = spend.reserve(get_engine(), MODEL, SESSION_RESERVE_MICRODOLLARS)
    except spend.SpendLimitExceeded:
        await client.close(code=4429, reason="limit")
        return
    import websockets
    audio_ms = 0
    settled = False

    def settle():
        nonlocal settled
        if settled:
            return
        settled = True
        cost = min(SESSION_RESERVE_MICRODOLLARS, math.ceil(audio_ms / 1000 * 50))
        try:
            spend.settle(get_engine(), reservation, cost, input_tokens=0, cached_tokens=0, output_tokens=0)
        except Exception:
            pass

    try:
        async with websockets.connect(meta_realtime_url(), max_size=4_000_000) as meta:
            await meta.send(json.dumps(handshake(key, language)))
            try:
                ack = json.loads(await asyncio.wait_for(meta.recv(), timeout=10))
            except (asyncio.TimeoutError, ValueError):
                await client.close(code=4503, reason="handshake")
                return
            if "sessionId" not in ack:
                await client.close(code=4503, reason="handshake")
                return

            async def browser_to_meta():
                await client.send_text(json.dumps({"type": "ready"}))
                while True:
                    message = await client.receive()
                    if message["type"] == "websocket.disconnect":
                        raise WebSocketDisconnect()
                    if message.get("bytes") is not None:
                        if len(message["bytes"]) > MAX_FRAME_BYTES:
                            continue
                        await meta.send(message["bytes"])
                    elif (message.get("text") or "") == '{"type":"endStream"}':
                        await meta.send(json.dumps({"type": "endStream"}))
                        return

            async def meta_to_browser():
                nonlocal audio_ms
                async for raw in meta:
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        continue
                    kind = event.get("type")
                    if kind == "audioProgress":
                        audio_ms = max(audio_ms, int(event.get("audioProcessedMs") or 0))
                        continue
                    if kind in ("transcript", "speechComplete", "speechStart", "speechEnd", "error"):
                        await client.send_text(json.dumps({k: event.get(k) for k in ("type", "transcript", "turnId", "final", "message") if event.get(k) is not None}))
                    if kind == "error":
                        return

            pump = [
                asyncio.ensure_future(browser_to_meta()),
                asyncio.ensure_future(meta_to_browser()),
            ]
            try:
                await asyncio.wait_for(asyncio.wait(pump, return_when=asyncio.FIRST_COMPLETED), timeout=MAX_SESSION_SECONDS)
            except asyncio.TimeoutError:
                pass
            finally:
                for task in pump:
                    task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await client.close(code=4503, reason="upstream")
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        settle()
        try:
            await client.close(code=1000)
        except (RuntimeError, WebSocketDisconnect):
            pass
