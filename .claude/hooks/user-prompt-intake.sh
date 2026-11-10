#!/usr/bin/env bash
# AEGIS UserPromptSubmit: read-only state intake. Never append observations here.
set -uo pipefail
REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BRANCH=$(git -C "$REPO" branch --show-current 2>/dev/null || echo '?')
SRC_CHANGED=$(git -C "$REPO" diff --name-only 2>/dev/null | grep -cE '\.(ts|rs|py)$' || true)
STAGED=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
CHAIN_MJS="$REPO/.claude/metacog/chain.mjs"
CHAIN_DATA="$REPO/.claude/metacog/chain.jsonl"
CERT='{"status":"UNKNOWN","is_valid":null,"entry_count":null,"terminal_hash":null,"broken_at":null}'
# 'certify' only reads chain data; 'observe' and 'seal' mutate and are forbidden
# as implicit UserPromptSubmit side effects. Absence or failure is UNKNOWN.
if [[ -f "$CHAIN_MJS" && -f "$CHAIN_DATA" ]]; then
  observed=$(node "$CHAIN_MJS" certify 2>/dev/null) || observed=''
  if [[ -n "$observed" ]]; then
    CERT=$(OBSERVED="$observed" python3 - <<'PY'
import json, os
try:
    data = json.loads(os.environ["OBSERVED"])
    valid = data.get("is_valid")
    if not isinstance(valid, bool):
        raise ValueError("invalid certification")
    print(json.dumps({"status": "VERIFIED" if valid else "FAILED",
                      "is_valid": valid,
                      "entry_count": data.get("entry_count"),
                      "terminal_hash": data.get("terminal_hash"),
                      "broken_at": data.get("broken_at")}))
except Exception:
    print('{"status":"UNKNOWN","is_valid":null,"entry_count":null,"terminal_hash":null,"broken_at":null}')
PY
)
  fi
fi
BRANCH="$BRANCH" SRC_CHANGED="${SRC_CHANGED:-0}" STAGED="${STAGED:-0}" CERT="$CERT" python3 - <<'PY'
import json, os
try:
    cert = json.loads(os.environ["CERT"])
except Exception:
    cert = {"status":"UNKNOWN"}
status = cert.get("status", "UNKNOWN")
count = cert.get("entry_count")
hashval = cert.get("terminal_hash")
context = (
    "AEGIS READ-ONLY PREFLIGHT | branch:" + os.environ["BRANCH"] +
    " | changed-src:" + os.environ["SRC_CHANGED"] +
    " | staged:" + os.environ["STAGED"] + "\n" +
    "Metacognition certificate: " + status +
    " | entries:" + (str(count) if isinstance(count, int) else "UNKNOWN") +
    " | hash:" + ((hashval or "UNKNOWN")[:12]) + "\n" +
    "No prompt-triggered observation was appended; missing or invalid evidence is not PASS. " +
    "CI, formal proof and merge require separate source-bound verification."
)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit", "additionalContext": context}}))
PY
