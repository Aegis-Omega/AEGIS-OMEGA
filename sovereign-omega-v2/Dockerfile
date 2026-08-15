# AEGIS-Ω — aegis-vertex Cloud Run service (Python bridge)
# The TypeScript governance frontend is built and served separately (hub/).
# This image contains only the Python layer — no npm build needed.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (includes anthropic SDK for live swarm mode)
COPY python/requirements.txt ./python/requirements.txt
RUN pip install --no-cache-dir -r python/requirements.txt

# Copy the entire Python bridge layer
COPY python/ ./python/

# Data directory for checkpoint persistence
RUN mkdir -p /app/data

# Cloud Run injects PORT env var; bridge reads it via os.environ.get('PORT', ...)
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

ENV SOVEREIGN_BRIDGE_PORT=8080
ENV AEGIS_CHECKPOINT_PATH=/app/data/aegis_checkpoint.json

WORKDIR /app/python
CMD ["python", "omega_bridge.py"]
