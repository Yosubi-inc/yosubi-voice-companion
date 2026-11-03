# Multi-stage: static Next.js export + FastAPI backend serving it same-origin.
FROM node:20-alpine AS web
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
ARG NEXT_PUBLIC_DEMO_API_TOKEN=""
ARG NEXT_PUBLIC_DEMO_OFFLINE="0"
ARG NEXT_PUBLIC_TTS_URL=""
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/backend:/srv

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY tts/requirements.txt ./tts-requirements.txt
RUN pip install --no-cache-dir -r tts-requirements.txt

COPY backend/ ./backend/
COPY tts/ ./tts/
RUN python -c "from transformers import VitsModel, VitsTokenizer; [VitsTokenizer.from_pretrained(c) or VitsModel.from_pretrained(c) for c in ('facebook/mms-tts-eng', 'facebook/mms-tts-spa')]"
COPY --from=web /build/frontend/out ./frontend/out
COPY start.sh ./start.sh

RUN chmod +x ./start.sh \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8000

CMD ["./start.sh"]
