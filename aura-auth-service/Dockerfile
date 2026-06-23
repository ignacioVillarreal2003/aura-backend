FROM python:3.13-slim

WORKDIR /application

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs

RUN python manage.py collectstatic --noinput

# Normalize line endings (in case the repo was checked out on Windows) and make
# the entrypoint executable.
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/application/docker-entrypoint.sh"]

CMD ["gunicorn", "authservice.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--worker-class", "gthread", "--workers", "2", "--threads", "4", "--timeout", "60"]
