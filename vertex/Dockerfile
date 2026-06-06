FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    anthropic==0.52.0 \
    redis[asyncio]==5.1.0 \
    httpx==0.27.0 \
    pyyaml==6.0.2

COPY serve.py .
COPY ../agents /app/agents

ENV PORT=8080
EXPOSE 8080

CMD ["python", "serve.py"]
