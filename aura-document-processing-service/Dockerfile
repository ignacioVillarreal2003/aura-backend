FROM python:3.13-slim

WORKDIR /application

COPY requirements/requirements.txt .

RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Pre-descarga de modelos HuggingFace (splitting / embedding / rerank) en build-time
# para que el arranque del contenedor no dependa de la red.
# HF_TOKEN es opcional en build (acelera la descarga); el runtime lo toma de .env.docker.
COPY scripts/download_models.py ./scripts/download_models.py
ARG HF_TOKEN=""
ARG HF_MODELS="sentence-transformers/paraphrase-multilingual-mpnet-base-v2 intfloat/multilingual-e5-large BAAI/bge-reranker-v2-m3"
RUN python ./scripts/download_models.py ${HF_MODELS}

COPY ./app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
