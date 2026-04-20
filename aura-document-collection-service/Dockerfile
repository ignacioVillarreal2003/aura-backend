FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM dependencies AS runtime

COPY . .

RUN chown -R app:app /app
USER app

EXPOSE 8000

ENV DJANGO_SETTINGS_MODULE=aura_document_collection_service.settings.production

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "aura_document_collection_service.wsgi:application"]
