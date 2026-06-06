#!/usr/bin/env bash
# AEGIS Agent Ecosystem — Quick-start runner
# Usage: ./agents/run.sh <role> "<task>"
# Examples:
#   ./agents/run.sh engineering "Review the constitutional proxy and identify any gaps"
#   ./agents/run.sh biz_dev "Draft an email to Anthropic partnerships team"
#   ./agents/run.sh marketing "Write a LinkedIn post about EU AI Act Article 12 compliance"
#   ./agents/run.sh compliance "Map AEGIS against NIST SP 800-53 AU-9 and AU-10"
#   ./agents/run.sh finance "Analyze cost structure for 10 enterprise customers"

set -euo pipefail

ROLE="${1:-engineering}"
TASK="${2:-List your capabilities and current operational status}"
CYCLES="${3:-3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Install deps if needed
if ! python3 -c "import httpx, yaml" 2>/dev/null; then
    echo "[agents] Installing dependencies..."
    pip install -q -r "$SCRIPT_DIR/requirements.txt"
fi

cd "$REPO_ROOT"
PROXY_URL="${PROXY_URL:-http://localhost:8080}" \
REDIS_URL="${REDIS_URL:-redis://localhost:6379}" \
AEGIS_DEFAULT_MODEL="${AEGIS_DEFAULT_MODEL:-claude-opus-4-8}" \
    python3 -m agents.coordinator run --role "$ROLE" --task "$TASK" --cycles "$CYCLES"
