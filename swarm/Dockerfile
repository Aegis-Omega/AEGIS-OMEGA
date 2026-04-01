# Dockerfile — SWARM server for Cloud Run
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY config.py server.py index.html ./

# Cloud Run injects PORT env var; uvicorn reads it
ENV PORT=8080

# NOTE: forager.py is NOT included in the container image.
# Run it locally or as a separate Cloud Run Job.
EXPOSE 8080

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port $PORT"]
