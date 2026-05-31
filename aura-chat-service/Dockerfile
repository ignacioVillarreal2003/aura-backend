FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

FROM base AS dependencies

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM dependencies AS runtime

COPY . .

RUN mkdir -p /app/.cache/huggingface && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status==200 else 1)"]

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "aura_chat_service.asgi:application"]
