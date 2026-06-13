FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/cache/huggingface \
    TIKTOKEN_CACHE_DIR=/opt/cache/tiktoken \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /application

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY requirements/requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

ARG TEXT_SPLITTER_HF_MODEL="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
ARG EMBEDDER_HF_MODEL=""
ARG RERANKER_MODEL="BAAI/bge-reranker-v2-m3"
ARG TIKTOKEN_ENCODING="cl100k_base"

COPY scripts/download_models.py ./scripts/download_models.py

RUN mkdir -p /opt/cache \
    && python scripts/download_models.py \
    --sentence-transformer "$TEXT_SPLITTER_HF_MODEL" \
    --sentence-transformer "$EMBEDDER_HF_MODEL" \
    --cross-encoder "$RERANKER_MODEL" \
    --tiktoken "$TIKTOKEN_ENCODING" \
    && chown -R appuser:appuser /opt/cache

COPY ./app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
