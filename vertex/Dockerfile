# AEGIS-Ω Agent Platform — Cloud Run service image.
# IMPORTANT: build context is the REPOSITORY ROOT (not vertex/), because the
# platform endpoints import the `agents` package and read `harness/skill_tree.json`.
# Build with:  docker build -f vertex/Dockerfile -t <img> .
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    anthropic==0.52.0 \
    redis[asyncio]==5.1.0 \
    httpx==0.27.0 \
    pyyaml==6.0.2

# serve.py at /app, agents package at /app/agents, harness data at /app/harness.
# evolution.py computes _REPO_ROOT = dirname(agents) = /app, so it finds
# /app/harness/skill_tree.json. serve.py's path setup adds /app to sys.path.
COPY vertex/serve.py /app/serve.py
COPY agents /app/agents
COPY harness /app/harness

ENV PORT=8080
EXPOSE 8080

CMD ["python", "serve.py"]
