FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    CACHE_DIR=/data/cache RUNS_DIR=/data/runs TEMPLATES_DIR=/data/templates/sublimation

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

RUN useradd -r -u 1000 uvmix && mkdir -p /data && chown uvmix /data
USER uvmix
VOLUME /data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
