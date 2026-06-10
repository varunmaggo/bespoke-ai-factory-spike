# Build context: repo root (the service runs as the `services.transform` package)
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/transform/ ./services/transform/

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["uvicorn", "services.transform.main:app", "--host", "0.0.0.0", "--port", "8003"]
