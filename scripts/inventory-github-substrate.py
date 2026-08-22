#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.sdk.github_substrate import build_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description='Build deterministic GitHub substrate manifest')
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--candidate-sha', required=True)
    parser.add_argument('--historical-observations')
    parser.add_argument('--output')
    args = parser.parse_args()

    historical = None
    if args.historical_observations:
        historical = json.loads(Path(args.historical_observations).read_text(encoding='utf-8'))
        if not isinstance(historical, list):
            raise SystemExit('historical observations must be a JSON list')

    manifest = build_manifest(
        Path(args.repo_root).resolve(),
        candidate_sha=args.candidate_sha,
        historical_observations=historical,
    )
    encoded = json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n'
    if args.output:
        Path(args.output).write_text(encoded, encoding='utf-8')
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
