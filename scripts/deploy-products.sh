#!/usr/bin/env bash
# AEGIS Commercial Products — One-Command Deploy to Vercel
# Run this from your LOCAL machine (not the cloud container)
# Requires: vercel CLI installed + logged in; provider credentials stay server-side
#
# Usage:
#   bash scripts/prepare-deployment.sh --build
#   bash scripts/deploy-products.sh
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

# Vite embeds VITE_* values into public JavaScript. Never forward provider
# credentials to browser deployments; configure the existing server-side proxy.
for name in VITE_DASHSCOPE_API_KEY VITE_CLAUDE_API_KEY VITE_OPENAI_API_KEY VITE_AZURE_OPENAI_API_KEY; do
  [[ -z "${!name:-}" ]] || die "$name is a provider credential exposed to browser builds; remove it before deploying"
done
bash "$REPO_ROOT/scripts/prepare-deployment.sh"

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
  # Product-local packages and the separately locked shared package are both
  # required: TypeScript follows @shared imports outside each product root.
  if [[ -f package-lock.json ]]; then
    npm ci --silent --include=dev
  else
    npm install --silent
  fi
  if [[ "$product" == "platform-picker" || "$product" == "hook-generator" || "$product" == "content-calendar" ]]; then
    [[ -f "$REPO_ROOT/packages/shared/package-lock.json" ]] || die "Missing shared lockfile"
    npm ci --silent --include=dev --prefix "$REPO_ROOT/packages/shared"
  fi
  npm run build --silent
  log "$product local build OK"

  # Deploy to Vercel production. Canonical domains are documented in DEPLOY.md;
  # the deployment URL printed by Vercel should be aliased to the matching domain.
  vercel --prod --yes 2>&1 | tail -5

  log "$product production target: ${PRODUCTION_URLS[$product]}"

  log "$product deployment command completed; public surface not yet verified"
  echo ""
done

cd "$REPO_ROOT"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "▸ Validating actual public product surfaces (not just Vercel READY)"
python3 "$REPO_ROOT/scripts/product_surface_gate.py" || die "Production surface verification failed — do not claim deployment complete"

log "All products deployed!"
echo ""
echo "Provider credentials must be configured on the existing server-side inference service."
echo "Payment verification remains in the existing server-side payment functions."
