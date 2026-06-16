FROM python:3.13-slim

WORKDIR /application

# Build from the exact-pinned deploy lock for reproducible images (M1).
COPY requirements/requirements.lock.txt ./

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ \
    && pip install --no-cache-dir -r requirements.lock.txt \
    && apt-get purge -y g++ \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY ./app ./app

RUN addgroup --system aura && adduser --system --ingroup aura aura
USER aura

EXPOSE 8000

# Number of uvicorn worker processes. Default 1 so the in-process LLM concurrency
# limiter (LLM_MAX_CONCURRENCY) is a true global cap; raise WEB_CONCURRENCY only
# if the Ollama backend can serve workers*LLM_MAX_CONCURRENCY concurrent calls.
ENV WEB_CONCURRENCY=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"]

# Shell form so ${WEB_CONCURRENCY} is expanded at runtime.
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY}
