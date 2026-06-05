#!/usr/bin/env bash
# AEGIS Commercial Products — One-Command Deploy to Vercel
# Run this from your LOCAL machine (not the cloud container)
# Requires: vercel CLI installed + logged in + DASHSCOPE API key
#
# Usage:
#   export DASHSCOPE_KEY="sk-XXXXXXXXXXXXXXXX"   # your DashScope API key
#   bash scripts/prepare-deployment.sh --build
#   bash scripts/deploy-products.sh
#
# Optional:
#   ALLOW_MISSING_DASHSCOPE=1 bash scripts/deploy-products.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHSCOPE_KEY="${DASHSCOPE_KEY:-}"
ALLOW_MISSING_DASHSCOPE="${ALLOW_MISSING_DASHSCOPE:-0}"
PRODUCTS=("platform-picker" "hook-generator" "content-calendar" "hub")

declare -A PRODUCTION_URLS=(
  [platform-picker]="https://platform.aegisomega.com"
  [hook-generator]="https://hooks.aegisomega.com"
  [content-calendar]="https://calendar.aegisomega.com"
  [hub]="https://aegisomega.com"
)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()    { echo -e "${GREEN}✓${NC} $*"; }
warn()   { echo -e "${YELLOW}⚠${NC} $*"; }
die()    { echo -e "${RED}✗ ERROR:${NC} $*"; exit 1; }

# ── Pre-flight checks ──────────────────────────────────────────────────────────
command -v vercel >/dev/null 2>&1 || die "vercel CLI not installed. Run: npm i -g vercel"
vercel whoami >/dev/null 2>&1 || die "Not logged in to Vercel. Run: vercel login"

if [[ -z "$DASHSCOPE_KEY" && "$ALLOW_MISSING_DASHSCOPE" != "1" ]]; then
  die "DASHSCOPE_KEY not set. Set DASHSCOPE_KEY=sk-... or rerun with ALLOW_MISSING_DASHSCOPE=1 for a build-only deploy."
fi

if [[ "$ALLOW_MISSING_DASHSCOPE" == "1" ]]; then
  bash "$REPO_ROOT/scripts/prepare-deployment.sh"
else
  bash "$REPO_ROOT/scripts/prepare-deployment.sh" --require-secrets
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  AEGIS Ω — Deploying commercial products to Vercel"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── Deploy each product ────────────────────────────────────────────────────────
for product in "${PRODUCTS[@]}"; do
  dir="$REPO_ROOT/$product"
  [[ -d "$dir" ]] || { warn "Directory $product not found, skipping"; continue; }

  echo "▸ Deploying $product..."
  cd "$dir"

  # Build locally first to catch errors
  npm install --silent
  npm run build --silent
  log "$product build OK"

  # Deploy to Vercel production. Canonical domains are documented in DEPLOY.md;
  # the deployment URL printed by Vercel should be aliased to the matching domain.
  if [[ -n "$DASHSCOPE_KEY" && "$product" != "hub" ]]; then
    vercel --prod --yes \
      -e "VITE_DASHSCOPE_API_KEY=$DASHSCOPE_KEY" \
      -e "VITE_DASHSCOPE_MODEL=qwen-plus" \
      -e "VITE_HUB_URL=https://aegisomega.com" \
      2>&1 | tail -5
  else
    vercel --prod --yes 2>&1 | tail -5
  fi

  log "$product production target: ${PRODUCTION_URLS[$product]}"

  log "$product deployed ✓"
  echo ""
done

cd "$REPO_ROOT"
echo "═══════════════════════════════════════════════════════"
echo ""
log "All products deployed!"
echo ""
echo "Next steps:"
echo "  1. Note the Vercel deployment URLs from above"
echo "  2. Alias each deployment to its canonical aegisomega.com domain"
echo "  3. Set up Lemon Squeezy products (see DEPLOY.md):"
echo "     - Single tool          → \$19"
echo "     - Starter (any 2)     → \$29"
echo "     - Full Toolkit        → \$39"
echo ""
echo "  4. Point Lemon Squeezy redirects to https://aegisomega.com/success?order_id={order_id}"
echo ""
