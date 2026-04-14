FROM python:3.13-slim

WORKDIR /application

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "authservice.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
