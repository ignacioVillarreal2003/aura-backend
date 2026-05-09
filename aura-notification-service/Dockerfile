FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=aura_notification_service.settings.production

WORKDIR /application

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs staticfiles

EXPOSE 8000

# `gthread` workers + multiple threads keep the SSE long-poll connections alive
# while still serving regular REST traffic. Tune via env if needed.
CMD ["gunicorn", \
     "aura_notification_service.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--threads", "8", \
     "--worker-class", "gthread", \
     "--timeout", "120", \
     "--keep-alive", "30"]
