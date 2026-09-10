# AEGIS-Ω Agent Platform — Cloud Run service image.
# IMPORTANT: build context is the REPOSITORY ROOT (not vertex/), because the
# platform endpoints import the `agents` package and read `harness/skill_tree.json`.
# Build with: docker build -f vertex/Dockerfile -t <img> .
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    anthropic==0.52.0 \
    redis[asyncio]==5.1.0 \
    httpx==0.27.0 \
    pyyaml==6.0.2 \
    anyio==4.6.2

# runtime.py installs a standard-library outer authority membrane before the
# FastAPI application can observe paid or webhook requests. Missing authority
# configuration therefore fails closed rather than silently becoming public.
COPY vertex/serve.py /app/serve.py
COPY vertex/authority_boundary.py /app/authority_boundary.py
COPY vertex/runtime.py /app/runtime.py
COPY agents /app/agents
COPY harness /app/harness

ENV PORT=8080
EXPOSE 8080

CMD ["python", "runtime.py"]
