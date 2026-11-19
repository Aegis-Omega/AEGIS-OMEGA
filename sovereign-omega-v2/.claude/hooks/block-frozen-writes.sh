#!/usr/bin/env bash
# Compatibility entrypoint: all Write/Edit checks use the same stdin JSON guard.
set -euo pipefail
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HOOK_DIR/frozen-write-guard.py"
