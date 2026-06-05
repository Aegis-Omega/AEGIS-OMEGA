#!/usr/bin/env bash
# AEGIS Ω — full-stack deployment readiness preflight.
#
# This script is intentionally non-interactive so it can run locally, in CI,
# or in a release container before production deployment. It validates the
# release surface without requiring secrets unless --require-secrets is passed.
#
# Usage:
#   bash scripts/prepare-deployment.sh
#   bash scripts/prepare-deployment.sh --build --docker-config
#   bash scripts/prepare-deployment.sh --require-secrets

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_BUILDS=0
CHECK_DOCKER=0
REQUIRE_SECRETS=0

PRODUCT_APPS=(hub platform-picker hook-generator content-calendar)
FULL_STACK_APPS=(hub platform-picker hook-generator content-calendar cockpit studio enterprise aegisomega-webgpu)
RUNTIME_DIR="sovereign-omega-v2"
REQUIRED_SECRET_VARS=(DASHSCOPE_KEY VITE_LS_LINK_SINGLE VITE_LS_LINK_STARTER VITE_LS_LINK_FULL)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
  cat <<'USAGE'
AEGIS Ω deployment readiness preflight

Options:
  --build             Run npm builds for all full-stack frontend apps.
  --docker-config     Validate docker compose syntax if Docker Compose is available.
  --require-secrets   Fail when production deployment secrets are missing.
  -h, --help          Show this help text.
USAGE
}

log() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
info() { echo -e "${BLUE}▸${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; FAILURES=$((FAILURES + 1)); }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) RUN_BUILDS=1 ;;
    --docker-config) CHECK_DOCKER=1 ;;
    --require-secrets) REQUIRE_SECRETS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 2 ;;
  esac
  shift
done

FAILURES=0

require_file() {
  local file="$1"
  if [[ -f "$REPO_ROOT/$file" ]]; then
    log "Found $file"
  else
    fail "Missing $file"
  fi
}

require_dir() {
  local dir="$1"
  if [[ -d "$REPO_ROOT/$dir" ]]; then
    log "Found $dir/"
  else
    fail "Missing $dir/"
  fi
}

check_command_or_warn() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    log "Command available: $cmd"
    return 0
  fi
  warn "Command not found: $cmd"
  return 1
}

check_no_conflict_markers() {
  info "Checking for unresolved merge conflict markers"
  if rg -n '^<<<<<<< |^=======\r?$|^>>>>>>> ' \
    -g '!node_modules' \
    -g '!dist' \
    -g '!build' \
    -g '!target' \
    "$REPO_ROOT" >/tmp/aegis-conflict-markers.txt; then
    cat /tmp/aegis-conflict-markers.txt
    fail "Unresolved merge conflict markers detected"
  else
    log "No unresolved merge conflict markers detected"
  fi
}

check_app() {
  local app="$1"
  require_dir "$app"
  require_file "$app/package.json"

  if [[ -f "$REPO_ROOT/$app/vite.config.ts" ]]; then
    log "$app has Vite config"
  else
    warn "$app has no vite.config.ts"
  fi

  if [[ -f "$REPO_ROOT/$app/vercel.json" ]]; then
    log "$app has Vercel config"
  else
    warn "$app has no vercel.json; deploy may rely on dashboard defaults"
  fi

  if [[ -f "$REPO_ROOT/$app/.env.example" ]]; then
    log "$app has .env.example"
  else
    warn "$app has no .env.example"
  fi
}

check_secrets() {
  info "Checking deployment secrets policy"
  for var_name in "${REQUIRED_SECRET_VARS[@]}"; do
    if [[ -n "${!var_name:-}" ]]; then
      log "$var_name is set"
    elif [[ "$REQUIRE_SECRETS" -eq 1 ]]; then
      fail "$var_name is required but not set"
    else
      warn "$var_name is not set (allowed without --require-secrets)"
    fi
  done
}

run_frontend_builds() {
  info "Running full-stack frontend builds"
  for app in "${FULL_STACK_APPS[@]}"; do
    if [[ ! -f "$REPO_ROOT/$app/package.json" ]]; then
      warn "Skipping $app: package.json not found"
      continue
    fi

    info "Building $app"
    (
      cd "$REPO_ROOT/$app"
      if [[ -f package-lock.json ]]; then
        npm ci
      else
        npm install
      fi
      npm run build
    ) || fail "$app build failed"
  done
}

check_docker_compose() {
  info "Checking Docker Compose configuration"
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    (cd "$REPO_ROOT" && docker compose config >/tmp/aegis-docker-compose.yml) \
      && log "docker compose config passed" \
      || fail "docker compose config failed"
  elif command -v docker-compose >/dev/null 2>&1; then
    (cd "$REPO_ROOT" && docker-compose config >/tmp/aegis-docker-compose.yml) \
      && log "docker-compose config passed" \
      || fail "docker-compose config failed"
  else
    warn "Docker Compose not installed; skipping compose syntax check"
  fi
}

cd "$REPO_ROOT"

echo "═══════════════════════════════════════════════════════"
echo "  AEGIS Ω — Full-Stack Deployment Readiness Preflight"
echo "═══════════════════════════════════════════════════════"
echo ""

check_command_or_warn git >/dev/null || true
check_command_or_warn node >/dev/null || true
check_command_or_warn npm >/dev/null || true
check_command_or_warn rg >/dev/null || fail "ripgrep is required for conflict-marker checks"

require_file README.md
require_file DEPLOY.md
require_file docker-compose.yml
require_file vercel.json
require_file "$RUNTIME_DIR/Dockerfile"
require_file "$RUNTIME_DIR/.env.example"
require_file "$RUNTIME_DIR/package.json"

info "Checking product apps"
for app in "${PRODUCT_APPS[@]}"; do
  check_app "$app"
done

info "Checking operator and observability apps"
for app in cockpit studio enterprise aegisomega-webgpu; do
  check_app "$app"
done

check_no_conflict_markers
check_secrets

if [[ "$CHECK_DOCKER" -eq 1 ]]; then
  check_docker_compose
else
  warn "Docker Compose syntax check skipped (pass --docker-config to enable)"
fi

if [[ "$RUN_BUILDS" -eq 1 ]]; then
  run_frontend_builds
else
  warn "Frontend builds skipped (pass --build to enable)"
fi

if [[ "$FAILURES" -ne 0 ]]; then
  echo ""
  echo -e "${RED}Deployment readiness failed with ${FAILURES} issue(s).${NC}"
  exit 1
fi

echo ""
log "Deployment readiness preflight passed"
