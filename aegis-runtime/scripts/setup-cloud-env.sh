#!/usr/bin/env bash
# AEGIS-Ω Cloud Environment Setup
# Sets non-secret environment variables for the cloud deployment.
# Usage: source scripts/setup-cloud-env.sh
#
# SECURITY: Do NOT add API keys or secrets to this file.
# Set VITE_DASHSCOPE_KEY separately via your secrets manager or CI dashboard.
# This script only sets infrastructure / routing configuration.

set -euo pipefail

# ─── DashScope API ───────────────────────────────────────────
export VITE_DASHSCOPE_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
export VITE_DASHSCOPE_MODEL="qwen-plus"
# export VITE_DASHSCOPE_KEY=  ← set this via secrets manager, never here

# ─── Runtime version pins ────────────────────────────────────
export VITE_SCHEMA_VERSION="1.0.0"
export VITE_PROJECTION_COMPILER_VERSION="1.0.0"
export VITE_CALIBRATION_MODEL_VERSION="1.0.0"
export VITE_APP_VERSION="0.5.3"

# ─── AEGIS Runtime ───────────────────────────────────────────
export AEGIS_CHECKPOINT_PATH="/app/data/aegis_checkpoint.json"
export SOVEREIGN_BRIDGE_PORT="7890"
export AEGIS_GOSSIP_UDP_PORT="9090"

# ─── Gate parameters ─────────────────────────────────────────
export VITE_GATE_ALPHA="0.05"
export VITE_GATE_RHO="0.5"

# ─── VCG Calibration ─────────────────────────────────────────
export VITE_VCG_WINDOW_SIZE="500"
export VITE_VCG_MIN_GATE_WINDOW="100"
export VITE_VCG_ALERT_THRESHOLD="0.35"
export VITE_VCG_SUSPEND_THRESHOLD="0.50"

# ─── Risk Budget ─────────────────────────────────────────────
export VITE_RISK_BUDGET_GLOBAL="1.0"
export VITE_RISK_BUDGET_MAX_ROUNDS="1000"
export VITE_RISK_BUDGET_DECAY_LAMBDA="0.0000000139"

echo "[AEGIS-Ω] Cloud environment configured."
echo "  Bridge port   : ${SOVEREIGN_BRIDGE_PORT}"
echo "  Checkpoint    : ${AEGIS_CHECKPOINT_PATH}"
echo "  Gossip UDP    : ${AEGIS_GOSSIP_UDP_PORT}"
echo "  Schema version: ${VITE_SCHEMA_VERSION}"
echo ""
echo "  REMINDER: Set VITE_DASHSCOPE_KEY via your secrets manager before starting."
