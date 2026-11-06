# AEGIS-Ω — aegis-vertex Cloud Run service (Python bridge)
# Build context is repository root; only explicitly copied runtime slices enter the image.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY sovereign-omega-v2/python/requirements.txt ./python/requirements.txt
RUN pip install --no-cache-dir -r python/requirements.txt

COPY sovereign-omega-v2/python/ ./python/

# Bounded recovered archive runtime surface. Do not copy ARC datasets, benchmark
# corpora, provider proxies, or historical state into this production image.
COPY harness/__init__.py ./harness/__init__.py
COPY harness/sdk/__init__.py ./harness/sdk/__init__.py
COPY harness/sdk/archive_runtime.py ./harness/sdk/archive_runtime.py
COPY swarm_os/arc/dsl/ ./swarm_os/arc/dsl/
COPY swarm_os/swarm/swarm_core.py ./swarm_os/swarm/swarm_core.py
COPY swarm_os/swarm/config.py ./swarm_os/swarm/config.py
COPY swarm_os/biology/cybernetic_core.py ./swarm_os/biology/cybernetic_core.py

RUN mkdir -p /app/data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

ENV SOVEREIGN_BRIDGE_PORT=8080
ENV AEGIS_CHECKPOINT_PATH=/app/data/aegis_checkpoint.json
ENV PYTHONPATH=/app:/app/python

WORKDIR /app/python
CMD ["python", "bridge.py"]
