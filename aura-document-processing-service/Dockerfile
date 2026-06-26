FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/cache/huggingface \
    TIKTOKEN_CACHE_DIR=/opt/cache/huggingface/tiktoken \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HUB_DOWNLOAD_TIMEOUT=30 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /application

RUN python -m venv /opt/venv

COPY requirements/base.txt requirements/requirements.txt ./requirements/

RUN pip install --no-cache-dir -r requirements/requirements.txt

# The runtime .env is the single source of truth for which models get baked:
# whatever EMBEDDER_HUGGINGFACE_MODEL / TEXT_SPLITTER_* / RERANKER_MODEL_NAME the
# service loads at startup is exactly what download_models.py caches here.
ARG MODELS_ENV_FILE="env/.env.docker"
ARG TIKTOKEN_ENCODING="cl100k_base"

COPY scripts/download_models.py ./scripts/download_models.py
COPY ${MODELS_ENV_FILE} ./models.env

RUN mkdir -p /opt/cache \
    && python scripts/download_models.py \
    --env-file ./models.env \
    --tiktoken "$TIKTOKEN_ENCODING" \
    --docling-output /opt/cache/huggingface/docling \
    && rm -f ./models.env


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/cache/huggingface \
    TIKTOKEN_CACHE_DIR=/opt/cache/huggingface/tiktoken \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    READER_DOCLING_ARTIFACTS_PATH=/opt/cache/huggingface/docling \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /application

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=appuser:appuser /opt/cache /opt/cache

COPY ./app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
