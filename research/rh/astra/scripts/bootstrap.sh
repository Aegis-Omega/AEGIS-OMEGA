#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; PYTHON_BIN="${PYTHON_BIN:-python3}"; VENV="${AEGIS_ASTRA_VENV:-$ROOT/.venv}"
"$PYTHON_BIN" -m venv "$VENV"; "$VENV/bin/python" -m pip install --upgrade pip; "$VENV/bin/pip" install -r "$ROOT/requirements-validator.txt"
[[ "${1:-}" == "--discovery" ]] && "$VENV/bin/pip" install -r "$ROOT/requirements-discovery.txt" || true
"$VENV/bin/python" "$ROOT/scripts/validate_obligations.py" --root "$ROOT"; (cd "$ROOT" && "$VENV/bin/python" -m pytest -q tests)
printf 'AEGIS Astra RH validator environment ready at %s\n' "$VENV"
