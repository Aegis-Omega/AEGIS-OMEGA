#!/usr/bin/env bash
set -euo pipefail
python -m pytest -q
python tools/fuzz_stress_v1.py
python -m compileall -q src tests tools
