# Build context: repo root (needs the shared `evals/` package)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY evals/ ./evals/
COPY services/eval/ ./services/eval/

ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "services.eval.main:app", "--host", "0.0.0.0", "--port", "8002"]
