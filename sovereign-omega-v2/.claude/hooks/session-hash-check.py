#!/usr/bin/env python3
"""Read-only, exit-code-bound constitutional hash check for SessionStart.

Never emit VERIFIED merely because stdout does not contain 'error'.
The verifier's documented exit codes are 0 PASS, 1 VIOLATION, 2 INCOMPLETE.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("python/gate.py", "python/dna.py", "python/router.py")
PASS_MARKER = "All frozen files present and hash-verified."


def classify(returncode: int, stdout: str, stderr: str) -> dict:
    if returncode == 0:
        if PASS_MARKER in stdout and all(f"OK:   {path}" in stdout for path in REQUIRED):
            return {"status": "VERIFIED", "message": "AEGIS frozen-file hashes verified (3/3, exit 0)."}
        return {"status": "UNKNOWN", "message": "AEGIS hash checker returned 0 without the required success receipt; no verification claim."}
    if returncode == 1:
        return {"status": "FAILED", "message": "AEGIS constitutional hash mismatch (exit 1); protected mutations HOLD."}
    if returncode == 2:
        return {"status": "INCOMPLETE", "message": "AEGIS constitutional files missing (exit 2); protected mutations HOLD."}
    return {"status": "UNKNOWN", "message": f"AEGIS hash checker unavailable/unexpected exit {returncode}; protected mutations HOLD."}


def main() -> int:
    try:
        run = subprocess.run(
            ["node", "scripts/verify-hashes.mjs"],
            cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
        )
        result = classify(run.returncode, run.stdout, run.stderr)
    except (OSError, subprocess.TimeoutExpired):
        result = {"status": "UNKNOWN", "message": "AEGIS constitutional verification unavailable; protected mutations HOLD."}
    print(json.dumps({
        "systemMessage": result["message"],
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": f"AEGIS_FROZEN_HASH_STATUS={result['status']}; only VERIFIED means all three source hashes match",
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
