#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.sdk.provider_session import build_provider_session  # noqa: E402


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("PAYLOAD_MUST_BE_OBJECT")
        result = build_provider_session(payload)
    except Exception as exc:
        sys.stdout.write(json.dumps({"outcome": "DENIED", "code": str(exc)}, sort_keys=True) + "\n")
        return 3
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
