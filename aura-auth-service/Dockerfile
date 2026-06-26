FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=aura_auth_service.settings.development

WORKDIR /application

# Non-root runtime user (matches the convention of the other services).
RUN addgroup --system app && adduser --system --ingroup app app

FROM base AS dependencies

# No system build deps needed: every requirement ships as a wheel
# (psycopg2-binary bundles libpq).
COPY requirements.txt .

RUN apt-get update && apt-get install -y \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

FROM dependencies AS runtime

COPY --chown=app:app . .

# collectstatic needs neither DB nor network. Normalize the entrypoint line
# endings (the repo may be checked out on Windows), make it executable, and
# hand ownership of everything to the unprivileged user.
RUN python manage.py collectstatic --noinput \
    && sed -i 's/\r$//' docker-entrypoint.sh \
    && chmod +x docker-entrypoint.sh \
    && chown -R app:app /application

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=5)"]

ENTRYPOINT ["/application/docker-entrypoint.sh"]

CMD ["gunicorn", "aura_auth_service.wsgi:application", "-c", "gunicorn.conf.py"]
