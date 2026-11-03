FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/backend \
    PORT=8000

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8000

CMD ["python", "-m", "app"]
