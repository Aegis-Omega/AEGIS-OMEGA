#!/usr/bin/env bash
# deploy.sh — Build and deploy SWARM server to Cloud Run
# Project: lifequestplatinum
# Service: swarm-server
# Usage: bash deploy.sh

set -euo pipefail

PROJECT="lifequestplatinum"
SERVICE="swarm-server"
REGION="us-central1"
IMAGE="gcr.io/${PROJECT}/${SERVICE}"

echo "[SWARM] Building Docker image: ${IMAGE}"
gcloud builds submit \
  --project="${PROJECT}" \
  --tag="${IMAGE}" \
  .

echo "[SWARM] Deploying to Cloud Run: ${SERVICE} (${REGION})"
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --min-instances=0 \
  --max-instances=3 \
  --memory=512Mi \
  --cpu=1 \
  --port=8080

echo
echo "[SWARM] Deployment complete."
echo "[SWARM] Service URL:"
gcloud run services describe "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --format="value(status.url)"
