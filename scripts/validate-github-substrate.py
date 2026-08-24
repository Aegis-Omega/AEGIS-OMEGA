#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.sdk.github_substrate import validate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate deterministic GitHub substrate manifest')
    parser.add_argument('--manifest', required=True)
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    result = validate_manifest(manifest)
    receipt = {
        'schema_version': '1.0.0',
        'receipt_kind': 'GITHUB_SUBSTRATE_VALIDATION_V1',
        'candidate_sha': manifest.get('candidate_sha'),
        'authority': 'EVIDENCE_ONLY_NOT_RUNNER_REGISTRATION_AUTHORITY',
        'registered_runner_inventory_status': manifest.get('registered_runner_inventory_status', 'NOT_CHECKED'),
        'valid': not result['violations'],
        'violations': result['violations'],
        'warnings': result['warnings'],
    }
    print(json.dumps(receipt, sort_keys=True, separators=(',', ':')))
    return 0 if receipt['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
