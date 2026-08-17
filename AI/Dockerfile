FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src ./src
COPY models ./models
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
EXPOSE 8100
CMD ["sh", "-c", "uvicorn reksa_ai.service:app --host 0.0.0.0 --port ${PORT:-8100}"]
