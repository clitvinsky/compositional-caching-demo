FROM python:3.11-slim AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY static/ static/

RUN mkdir -p /app/output /app/assets \
    && cp /app/static/maya_character.png /app/assets/source_character.png \
    && chown -R appuser:appuser /app

ENV IMAGE_OUTPUT_DIR=/app/output \
    WORKERS_ASSETS_DIR=/app/assets

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
