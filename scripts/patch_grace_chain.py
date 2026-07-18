#!/usr/bin/env python3
"""Apply the bounded grace-chain control-flow repair to platform_helpers.py.

This script exists because the target module is large and the broken functions
span one structural region. It refuses to edit unless the exact defect markers
are present, making the patch deterministic and fail-closed.
"""
from __future__ import annotations

from pathlib import Path

TARGET = Path("sovereign-omega-v2/python/platform_helpers.py")
START_MARKER = "def award_graces_for_cycle(cycle_id: str, artifacts: list, verdict: str) -> None:\n"
END_MARKER = "\ndef fetch_compliance_export(from_ts: str | None, to_ts: str | None, limit: int) -> list:\n"

REPLACEMENT = '''def award_graces_for_cycle(cycle_id: str, artifacts: list, verdict: str) -> None:
    """
    Award grace tokens through the ordered department sequence for one cycle.

    Only APPROVED and FLAG cycles award graces. QUARANTINE is fail-closed and
    emits no requests. Empty outputs are excluded while order is preserved.
    Supabase failures are bounded per request and never break later awards.
    """
    import urllib.request as _urG
    import sys

    if verdict not in ('APPROVED', 'FLAG'):
        return

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return

    active = [
        artifact['role']
        for artifact in artifacts
        if artifact.get('output', '').strip() and artifact.get('role')
    ]
    if not active:
        return

    rpc_url = f'{supabase_url}/rest/v1/rpc/award_grace'
    auth_headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    }

    for index, to_dept in enumerate(active):
        from_dept = active[index - 1] if index > 0 else None
        payload = json.dumps({
            'p_cycle_id': cycle_id,
            'p_from_dept': from_dept,
            'p_to_dept': to_dept,
            'p_graces': 1,
            'p_viability_score': None,
        }).encode()
        request = _urG.Request(
            rpc_url,
            data=payload,
            headers=auth_headers,
            method='POST',
        )
        try:
            with _urG.urlopen(request, timeout=3):
                pass
        except Exception as exc:
            print(f'[bridge] grace award failed ({to_dept}): {exc}', file=sys.stderr)


def query_fitness_trend(window: int = 10) -> dict:
    """Return read-only homeostasis diagnostics for the requested recent window."""
    return _fetch_dept_fitness_stats(window)

'''


def main() -> int:
    source = TARGET.read_text(encoding="utf-8")
    start = source.find(START_MARKER)
    end = source.find(END_MARKER, start + 1)
    if start < 0 or end < 0:
        raise SystemExit("grace-chain patch markers not found; refusing mutation")

    broken = source[start:end]
    required_defect_markers = (
        "if verdict == 'QUARANTINE':",
        "def query_fitness_trend(window: int = 10) -> dict:",
        "active = [a['role'] for a in artifacts",
        "rpc/award_grace",
    )
    missing = [marker for marker in required_defect_markers if marker not in broken]
    if missing:
        raise SystemExit(f"target no longer matches verified defect; missing {missing!r}")

    repaired = source[:start] + REPLACEMENT + source[end + 1:]
    TARGET.write_text(repaired, encoding="utf-8")
    print(f"patched {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
