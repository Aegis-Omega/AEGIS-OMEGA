#!/usr/bin/env bash
# AEGIS-Ω Shell Client
# Universal — runs anywhere curl exists. No SDK, no runtime.
# The constitutional protocol speaks JSON; every language speaks JSON.
#
# Usage:
#   ./client.sh "Enter EU fintech market Q4 2026" gtm
#   AEGIS_BASE_URL=https://aegisomega.workers.dev ./client.sh "objective" revenue

set -euo pipefail

BASE="${AEGIS_BASE_URL:-https://aegisomega.workers.dev}"
OBJECTIVE="${1:-Identify best revenue opportunity}"
MODE="${2:-revenue}"

echo "AEGIS-Ω  objective=\"$OBJECTIVE\"  mode=$MODE"
echo ""

RESPONSE=$(curl -sf "$BASE/platform/collaborate" \
  -H "Content-Type: application/json" \
  -d "{\"objective\":\"$OBJECTIVE\",\"mode\":\"$MODE\",\"live\":false}" \
  --max-time 60)

# Validate envelope
CONTRACT=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('contract_version',''))" 2>/dev/null || echo "")
if [ "$CONTRACT" != "1.0.0" ]; then
  echo "ERROR: unexpected contract_version: $CONTRACT" >&2
  exit 1
fi

REPLAY=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_replay_reconstructable',''))" 2>/dev/null || echo "")
if [ "$REPLAY" != "True" ]; then
  echo "ERROR: is_replay_reconstructable must be true" >&2
  exit 1
fi

# Extract data fields
DATA=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(json.dumps(d,indent=2))" 2>/dev/null)

CYCLE_ID=$(echo "$DATA" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cycle_id',''))" 2>/dev/null)
DEPTS=$(echo "$DATA"    | python3 -c "import sys,json; print(json.load(sys.stdin).get('departments_collaborated',0))" 2>/dev/null)
VERDICT=$(echo "$DATA"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('constitutional_audit',{}).get('verdict',''))" 2>/dev/null)
CHAIN=$(echo "$DATA"    | python3 -c "import sys,json; print(json.load(sys.stdin).get('chain_valid',False))" 2>/dev/null)

echo "cycle_id:    $CYCLE_ID"
echo "departments: $DEPTS"
echo "verdict:     $VERDICT"
echo "chain_valid: $CHAIN"
