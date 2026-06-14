FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

FROM base AS dependencies

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    libcairo2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM dependencies AS runtime

ARG WHISPER_MODEL_SIZE=small

RUN mkdir -p /app/.cache/huggingface \
    && python -c "from faster_whisper.utils import download_model; download_model('${WHISPER_MODEL_SIZE}')" \
    && chown app:app /app \
    && chown -R app:app /app/.cache

COPY --chown=app:app . .

USER app

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "aura_chat_service.asgi:application"]
