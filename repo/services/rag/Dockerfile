# Build context: repo root (the service runs as the `services.rag` package)
FROM python:3.11-slim

WORKDIR /app

# curl is used by the docker-compose healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/rag/ ./services/rag/

ENV PYTHONPATH=/app

EXPOSE 8001

CMD ["uvicorn", "services.rag.main:app", "--host", "0.0.0.0", "--port", "8001"]
