# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-hin \
        tesseract-ocr-mar \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts

RUN mkdir -p /app/storage/originals /app/storage/processed /app/storage/audio \
    && python -m py_compile app/main.py \
         app/core/config.py \
         app/providers/ocr.py \
         app/providers/ai.py \
         app/services/lesson_processing.py \
         scripts/jenkins_smoke.py \
    && python -c "from app.main import app; print('import_ok', app.title)"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
