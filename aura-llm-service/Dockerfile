FROM python:3.13-slim

WORKDIR /application

COPY requirements/requirements.txt .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./app ./app

RUN addgroup --system aura && adduser --system --ingroup aura aura
USER aura

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
