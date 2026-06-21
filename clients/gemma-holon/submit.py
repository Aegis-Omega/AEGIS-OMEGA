#!/usr/bin/env python3
"""
Submit a Gemma holon verdict to the AEGIS constitutional chain.

Usage:
    python submit.py                          # uses state.json defaults
    python submit.py '{"stress":0.9}'         # override specific fields
    echo '{"verdict":"APPROVED"}' | python submit.py -  # pipe verdict directly

The script:
  1. Loads state.json for bio_state defaults
  2. Optionally runs SovereignHD guard if torch is available
  3. POSTs to /platform/holon/validate
  4. Prints the chain_entry_hash
"""

import json
import sys
import os
import urllib.request as _ur
from pathlib import Path

HERE = Path(__file__).parent
CONFIG = json.loads((HERE / 'config.json').read_text())
STATE  = json.loads((HERE / 'state.json').read_text())

ENDPOINT = CONFIG['endpoint']
HOLON_ID = CONFIG['holon_id']


def load_bio_state(override_json: str | None = None) -> dict:
    bio = dict(STATE['bio_state'])
    if override_json:
        bio.update(json.loads(override_json))
    return bio


def guard_locally(bio_state: dict) -> dict:
    """Run SovereignHD if torch + sovereign_hd are available."""
    try:
        sys.path.insert(0, str(HERE.parent.parent / 'sovereign-omega-v2' / 'python'))
        import torch
        from sovereign_hd import SovereignHD
        guard = SovereignHD(d_k=CONFIG['d_k'], lambda_c=CONFIG['lambda_c'])
        qk = torch.randn(12, 12) / (CONFIG['d_k'] ** 0.5)
        return guard.guard_inference(qk, bio_state)
    except Exception:
        stress = bio_state.get('stress', 0.0)
        atp    = bio_state.get('atp', 2100)
        if stress >= 0.8 or atp <= 0:
            return {'verdict': 'FAILED', 'confidence': 0.99,
                    'reason_code': 'LIMBIC_EXHAUSTION_OR_ATP_DEPLETION'}
        return {'verdict': 'APPROVED', 'confidence': 0.85, 'reason_code': 'NOMINAL'}


def submit(bio_state: dict, verdict_override: dict | None = None) -> dict:
    result = verdict_override if verdict_override else guard_locally(bio_state)

    payload = json.dumps({
        'holon_id':   HOLON_ID,
        'verdict':    'APPROVED' if result.get('verdict') == 'APPROVED' else 'FAILED',
        'confidence': result.get('confidence', 0.5),
        'reason_code': result.get('reason_code', ''),
        'bio_state':  bio_state,
    }).encode()

    req = _ur.Request(ENDPOINT, data=payload,
                      headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with _ur.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        chain_hash = data.get('data', {}).get('chain_entry_hash', 'unavailable')
        print(json.dumps({'status': 'SUBMITTED', 'chain_entry_hash': chain_hash,
                          'verdict': result.get('verdict'), 'endpoint': ENDPOINT}, indent=2))
        return data
    except Exception as e:
        print(json.dumps({'status': 'OFFLINE', 'verdict': result.get('verdict'),
                          'reason': str(e), 'note': 'Deploy worker first: npx wrangler deploy'}, indent=2))
        return {}


if __name__ == '__main__':
    override = sys.argv[1] if len(sys.argv) > 1 else None
    piped    = sys.stdin.read().strip() if not sys.stdin.isatty() else None

    verdict_override = json.loads(piped) if piped and piped.startswith('{') else None
    bio_state = load_bio_state(override if not verdict_override else None)

    submit(bio_state, verdict_override)
