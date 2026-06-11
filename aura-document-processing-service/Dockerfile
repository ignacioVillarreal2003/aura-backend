FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/root/.cache/huggingface \
    TIKTOKEN_CACHE_DIR=/root/.cache/tiktoken \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /application

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Models baked into the image so containers start without downloading from the
# network. Defaults must stay in sync with .env.docker: the text splitter runs
# on Hugging Face, the active embedder is Ollama (served by the llm container,
# hence no EMBEDDER_HF_MODEL here) and the reranker defaults to bge-reranker.
ARG TEXT_SPLITTER_HF_MODEL="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
ARG EMBEDDER_HF_MODEL=""
ARG RERANKER_MODEL="BAAI/bge-reranker-v2-m3"
ARG TIKTOKEN_ENCODING="cl100k_base"

COPY scripts/download_models.py ./scripts/download_models.py

RUN python scripts/download_models.py \
    --sentence-transformer "$TEXT_SPLITTER_HF_MODEL" \
    --sentence-transformer "$EMBEDDER_HF_MODEL" \
    --cross-encoder "$RERANKER_MODEL" \
    --tiktoken "$TIKTOKEN_ENCODING"

COPY ./app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
