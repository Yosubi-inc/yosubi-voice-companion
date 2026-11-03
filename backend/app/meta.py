"""Offline-testable client for Meta's OpenAI-compatible chat endpoint."""
import json
import math
import os

import httpx
from fastapi import HTTPException

from app import spend
from app.resilience import retry


_UNAVAILABLE = {"en": "The assistant is unavailable right now.", "es": "El asistente no está disponible en este momento."}
_LIMIT = {"en": "The assistant spending limit has been reached.", "es": "Se ha alcanzado el límite de gasto del asistente."}
_MAX_OUTPUT = 1024


def model_call(call):
    if not os.getenv("MODEL_API_KEY"):
        raise HTTPException(503, detail=_UNAVAILABLE)
    return retry(call)


def _rates(model):
    if model == "muse-spark-1.3":
        return 1.25, 0.15, 4.25
    if model.startswith("muse-wonder"):
        return 4, 4, 20
    raise ValueError("Unsupported model pricing")


def _usage(usage, model):
    inputs = usage["prompt_tokens"]
    outputs = usage["completion_tokens"]
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    if any(type(n) is not int or n < 0 for n in (inputs, outputs, cached)) or cached > inputs:
        raise ValueError("Invalid model usage")
    in_rate, cache_rate, out_rate = _rates(model)
    cost = math.ceil((inputs - cached) * in_rate + cached * cache_rate + outputs * out_rate)
    return cost, inputs, cached, outputs


def chat(messages, *, engine, temperature=0.7, stream=False, client=None, reasoning_effort=None, model=None):
    """Send ordered messages; put stable system instructions first for caching.

    For streams, iteration yields text fragments. Usage is settled at the end;
    a missing usage record or interrupted response retains the reservation.
    """
    key = os.getenv("MODEL_API_KEY")
    if not key:
        raise HTTPException(503, detail=_UNAVAILABLE)
    model = model or os.getenv("MODEL_ID", "muse-spark-1.3")
    in_rate, _, out_rate = _rates(model)
    if not isinstance(messages, list) or not all(
        isinstance(m, dict) and set(m) == {"role", "content"}
        and m["role"] in ("system", "user", "assistant") and isinstance(m["content"], str)
        for m in messages
    ):
        raise ValueError("Messages must contain text roles and content")
    # A deliberately conservative allowance for text and message framing.
    input_bound = 4 * len(json.dumps(messages, ensure_ascii=True).encode("utf-8")) + 1024
    maximum = math.ceil(input_bound * in_rate + _MAX_OUTPUT * out_rate)
    effort = reasoning_effort or os.getenv("META_REASONING_EFFORT", "minimal")
    payload = {"model": model, "messages": messages, "temperature": temperature,
               "stream": stream, "max_tokens": _MAX_OUTPUT, "reasoning_effort": effort}
    if stream:
        payload["stream_options"] = {"include_usage": True}
    url = os.getenv("META_BASE_URL", "https://api.meta.ai/v1").rstrip("/") + "/chat/completions"
    own_client = client is None
    # Pin outbound to IPv4 for deterministic egress (v6 path untested).
    client = client or httpx.Client(timeout=60, transport=httpx.HTTPTransport(local_address="0.0.0.0"))

    def start():
        try:
            reservation = spend.reserve(engine, model, maximum)
        except spend.SpendLimitExceeded:
            raise HTTPException(429, detail=_LIMIT) from None
        request = client.build_request("POST", url, headers={"Authorization": f"Bearer {key}"}, json=payload)
        response = client.send(request, stream=stream)
        try:
            response.raise_for_status()
        except Exception:
            response.close()
            raise
        return reservation, response

    def settle(reservation, usage):
        cost, inputs, cached, outputs = _usage(usage, model)
        spend.settle(engine, reservation, cost, input_tokens=inputs, cached_tokens=cached, output_tokens=outputs)

    if not stream:
        try:
            reservation, response = retry(start)
            try:
                result = response.json()
                settle(reservation, result["usage"])
                return result["choices"][0]["message"]["content"]
            finally:
                response.close()
        finally:
            if own_client:
                client.close()

    def fragments():
        try:
            reservation, response = retry(start)
            try:
                usage = None
                emitted = []
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        if usage is None:
                            # Meta streams carry no usage event: settle a len/4 estimate.
                            text = "".join(emitted)
                            usage = {"prompt_tokens": max(1, math.ceil(len(json.dumps(messages)) / 4)),
                                     "completion_tokens": max(1, math.ceil(len(text) / 4))}
                        settle(reservation, usage)
                        return
                    event = json.loads(data)
                    if event.get("usage") is not None:
                        usage = event["usage"]
                    for choice in event.get("choices", []):
                        content = choice.get("delta", {}).get("content")
                        if content:
                            emitted.append(content)
                            yield content
                raise ValueError("Model stream ended before completion")
            finally:
                response.close()
        finally:
            if own_client:
                client.close()
    return fragments()
