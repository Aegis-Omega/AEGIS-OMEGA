#!/usr/bin/env bash
# PostToolUse: read-only tier diagnostics from the actual Write/Edit JSON event.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INPUT="$(cat)"
REL=$(ROOT="$ROOT" INPUT="$INPUT" python3 - <<'PY'
import json, os
from pathlib import Path
try:
    payload = json.loads(os.environ["INPUT"])
    if payload.get("tool_name", payload.get("toolName")) not in ("Write", "Edit"):
        raise ValueError("unexpected hook tool")
    args = payload.get("tool_input", payload.get("toolInput"))
    if not isinstance(args, dict):
        raise ValueError("missing tool input")
    raw = args.get("file_path", args.get("path"))
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("no file path")
    root = Path(os.environ["ROOT"]).resolve()
    p = Path(raw)
    if p.is_absolute():
        target = p.resolve()
    elif p.parts and p.parts[0] == root.name:
        target = (root.parent / p).resolve()
    else:
        target = (root / p).resolve()
    print(target.relative_to(root))
except (KeyError, TypeError, ValueError, OSError, RuntimeError, json.JSONDecodeError):
    raise SystemExit(2)
PY
) || { printf '%s\n' 'AEGIS tier-check UNKNOWN: invalid Write/Edit JSON event or path outside nested source'; exit 0; }
case "$REL" in
  src/*|test/*) ;;
  *) exit 0 ;;
esac
TARGET="$ROOT/$REL"
if [[ ! -f "$TARGET" ]]; then
  printf '%s\n' 'AEGIS tier-check UNKNOWN: target file absent after write/edit'
  exit 0
fi
T4_TERMS=(
  "planetary" "civilisational" "metamaterial" "consciousness"
  "multiverse" "PNAS" "thermodynamic liquefaction" "ego dissolution"
  "morphogenesis" "axiomatic arbitration" "quantum reality"
)
for term in "${T4_TERMS[@]}"; do
  if grep -Fqi -- "$term" "$TARGET"; then
    printf 'AEGIS tier warning: %s in %s; review taxonomy before promotion.\n' "$term" "$REL"
  fi
done
exit 0
