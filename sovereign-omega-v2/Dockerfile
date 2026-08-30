# AEGIS-Ω — aegis-vertex Cloud Run service (Python bridge)
# The TypeScript governance frontend is built and served separately (hub/).
# This image contains only the Python layer — no npm build needed.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (includes anthropic SDK for live swarm mode)
COPY sovereign-omega-v2/python/requirements.txt ./sovereign-omega-v2/python/requirements.txt
RUN pip install --no-cache-dir -r sovereign-omega-v2/python/requirements.txt

# Copy the live bridge plus the evidence/receipt SDK it invokes. The resident
# repository itself is an owned runtime clone under /app/data; .git is excluded
# from the image build context and canonical developer worktrees are never used.
COPY sovereign-omega-v2/python/ ./sovereign-omega-v2/python/
COPY harness/__init__.py ./harness/__init__.py
COPY harness/sdk/ ./harness/sdk/
COPY config/ ./config/
COPY models/ ./models/

# Data directory for checkpoint persistence
RUN mkdir -p /app/data

# Cloud Run injects PORT env var; bridge reads it via os.environ.get('PORT', ...)
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

ENV SOVEREIGN_BRIDGE_PORT=8080
ENV AEGIS_CHECKPOINT_PATH=/app/data/aegis_checkpoint.json
ENV AEGIS_RESIDENT_STATE_ROOT=/app/data/resident
ENV AEGIS_RESIDENT_REPOSITORY_ROOT=/app/data/repository
ENV AEGIS_RESIDENT_REPOSITORY_URL=https://github.com/Aegis-Omega/AEGIS-OMEGA.git
ENV AEGIS_RESIDENT_REPOSITORY_BRANCH=main
ENV PYTHONPATH=/app

WORKDIR /app/sovereign-omega-v2/python
CMD ["python", "resident_bootstrap.py"]
