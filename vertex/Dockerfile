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
    pyyaml==6.0.2 \
    anyio==4.6.2

# serve.py keeps the route/API compatibility surface. secure_serve.py overlays
# unconditional auth for sensitive routes and swaps in the concurrent audit
# chain. startup_guard.py refuses unauthenticated production startup.
COPY vertex/serve.py /app/serve.py
COPY vertex/secure_serve.py /app/secure_serve.py
COPY vertex/audit_chain_v2.py /app/audit_chain_v2.py
COPY vertex/startup_guard.py /app/startup_guard.py
COPY agents /app/agents
COPY harness /app/harness

ENV PORT=8080
EXPOSE 8080

CMD ["python", "startup_guard.py"]
