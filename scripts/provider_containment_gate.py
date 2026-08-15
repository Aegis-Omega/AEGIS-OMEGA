#!/usr/bin/env python3
"""AEGIS provider containment gate.

Fail closed on stale PR bases, unattributed provider mutations, and destructive
repository changes without path-level reconciliation and operator authority.

Provider-neutral by design: Claude, Codex, Gemini, NVIDIA, humans, bots, and
future agents cross the same repository boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

POLICY_PATH = Path('.aegis/provider-containment-policy.v1.json')
RECONCILIATION_PATH = Path('.aegis/reconciliation/provider-containment.json')
EVIDENCE_PATH = Path('provider-containment-evidence.json')


def run(*args: str, check: bool = True) -> str:
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(args)}\n{p.stderr.strip()}")
    return p.stdout.strip()


def die(code: str, detail: str, evidence: dict | None = None) -> None:
    payload = {"status": "REJECTED", "reason_code": code, "detail": detail}
    if evidence:
        payload.update(evidence)
    EVIDENCE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path, code: str) -> dict:
    if not path.is_file():
        die(code, f"required file missing: {path}")
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        die(code, f"invalid JSON in {path}: {exc}")
    if not isinstance(value, dict):
        die(code, f"{path} must contain a JSON object")
    return value


def topology_observation() -> tuple[int, str]:
    raw = run('git', 'ls-remote', '--heads', 'origin')
    lines = sorted(line.strip() for line in raw.splitlines() if line.strip())
    if not lines:
        die('TOPOLOGY_UNOBSERVABLE', 'git ls-remote returned no branch heads')
    canonical = ('\n'.join(lines) + '\n').encode('utf-8')
    return len(lines), hashlib.sha256(canonical).hexdigest()


def parse_name_status(base: str, head: str) -> list[dict]:
    raw = run('git', 'diff', '--name-status', '--find-renames', f'{base}...{head}')
    changes: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        status = parts[0]
        if status.startswith('R') and len(parts) >= 3:
            changes.append({'status': 'R', 'old_path': parts[1], 'path': parts[2]})
        elif len(parts) >= 2:
            changes.append({'status': status[0], 'path': parts[1]})
        else:
            die('DIFF_PARSE_ERROR', f'unrecognized name-status line: {line}')
    return changes


def discover_receipt(policy: dict, changes: list[dict]) -> tuple[Path, dict]:
    receipt_dir = policy.get('receipt_directory', '.aegis/provider-receipts').rstrip('/') + '/'
    touched = [
        c for c in changes
        if c.get('path', '').startswith(receipt_dir) and c.get('path', '').endswith('.json')
    ]
    modified_existing = [c['path'] for c in touched if c['status'] != 'A']
    if modified_existing:
        die(
            'PROVIDER_RECEIPT_NOT_APPEND_ONLY',
            f'existing provider receipts may not be modified/renamed/deleted: {modified_existing}',
        )
    added = [c['path'] for c in touched if c['status'] == 'A']
    if len(added) != 1:
        die('PROVIDER_RECEIPT_CARDINALITY', f'exactly one new provider receipt is required; found {added}')
    path = Path(added[0])
    receipt = load_json(path, 'PROVIDER_RECEIPT_MISSING')
    return path, receipt


def validate_hex64(value: str) -> bool:
    return len(value) == 64 and all(ch in '0123456789abcdefABCDEF' for ch in value)


def main() -> int:
    base = os.environ.get('BASE_SHA', '').strip()
    head = os.environ.get('HEAD_SHA', '').strip() or run('git', 'rev-parse', 'HEAD')
    if len(base) != 40 or len(head) != 40:
        die('INVALID_SHA_INPUT', f'BASE_SHA={base!r} HEAD_SHA={head!r}')

    policy = load_json(POLICY_PATH, 'POLICY_MISSING')

    merge_base = run('git', 'merge-base', base, head)
    if merge_base != base:
        die(
            'STALE_BASE_REJECTED',
            f'PR head is not based on exact base: merge_base={merge_base}, required_base={base}',
            {'base_sha': base, 'head_sha': head, 'merge_base': merge_base},
        )

    changes = parse_name_status(base, head)
    receipt_path, receipt = discover_receipt(policy, changes)
    missing = [k for k in policy['required_receipt_fields'] if k not in receipt]
    if missing:
        die('PROVIDER_RECEIPT_INCOMPLETE', f'missing receipt fields: {missing}')
    if receipt.get('base_sha') != base:
        die('RECEIPT_BASE_MISMATCH', f"receipt base_sha={receipt.get('base_sha')} required={base}")
    if str(receipt.get('receipt_id', '')).strip() != receipt_path.stem:
        die('RECEIPT_ID_PATH_MISMATCH', f"receipt_id must equal filename stem: {receipt_path.stem}")

    provider = str(receipt.get('provider', '')).strip()
    model = str(receipt.get('model', '')).strip()
    session_id = str(receipt.get('session_id', '')).strip()
    session_id_status = str(receipt.get('session_id_status', '')).strip()
    if not provider or not model or not session_id or not session_id_status:
        die('PROVIDER_ATTRIBUTION_EMPTY', 'provider, model, session_id, and session_id_status must be non-empty')

    changed_paths = [c['path'] for c in changes]
    deleted_paths = [c['path'] for c in changes if c['status'] == 'D']
    renamed_sources = [c['old_path'] for c in changes if c['status'] == 'R']
    destructive_paths = deleted_paths + renamed_sources

    critical_prefixes = tuple(policy.get('critical_prefixes', []))
    critical_files = set(policy.get('critical_files', []))
    critical_paths = sorted({
        p for p in changed_paths + renamed_sources
        if p in critical_files or p.startswith(critical_prefixes)
    })

    high_risk = (
        len(changed_paths) >= int(policy['high_risk_thresholds']['changed_paths'])
        or len(deleted_paths) >= int(policy['high_risk_thresholds']['deleted_paths'])
        or bool(renamed_sources)
        or bool(critical_paths)
    )

    if destructive_paths:
        if receipt.get('destructive_intent') is not True:
            die('DESTRUCTIVE_INTENT_UNDECLARED', f'deletions/renames detected: {destructive_paths}')
        approval = str(receipt.get('operator_approval_id', '')).strip()
        if not approval:
            die('OPERATOR_APPROVAL_REQUIRED', 'destructive change requires operator_approval_id')
        reconciliation = load_json(RECONCILIATION_PATH, 'DESTRUCTIVE_RECONCILIATION_MISSING')
        if str(reconciliation.get('operator_approval_id', '')).strip() != approval:
            die('RECONCILIATION_APPROVAL_MISMATCH', 'reconciliation operator_approval_id must equal provider receipt')
        dispositions = reconciliation.get('path_dispositions')
        if not isinstance(dispositions, dict):
            die('RECONCILIATION_INVALID', 'path_dispositions must be an object')
        allowed = set(policy.get('allowed_dispositions', []))
        missing_paths = [p for p in destructive_paths if p not in dispositions]
        invalid = {p: dispositions.get(p) for p in destructive_paths if dispositions.get(p) not in allowed}
        if missing_paths:
            die('DESTRUCTIVE_PATH_UNRECONCILED', f'missing dispositions for: {missing_paths}')
        if invalid:
            die('DESTRUCTIVE_DISPOSITION_INVALID', f'invalid dispositions: {invalid}')

        physical_delete_allowed = set(policy.get('physical_delete_permitted_dispositions', []))
        bad_deletes = {
            p: dispositions.get(p)
            for p in deleted_paths
            if dispositions.get(p) not in physical_delete_allowed
        }
        if bad_deletes:
            die(
                'PHYSICAL_DELETE_NOT_AUTHORIZED',
                f'physical deletion requires one of {sorted(physical_delete_allowed)}; got {bad_deletes}',
            )

    if high_risk and provider.lower() not in {'human', 'operator'}:
        reviewer = str(receipt.get('reviewer_provider', '')).strip()
        review_hash = str(receipt.get('review_receipt_hash', '')).strip()
        if not reviewer or reviewer.lower() == provider.lower():
            die('INDEPENDENT_PROVIDER_REVIEW_REQUIRED', f'provider={provider!r}, reviewer={reviewer!r}')
        if not validate_hex64(review_hash):
            die('REVIEW_RECEIPT_HASH_INVALID', 'review_receipt_hash must be 64 hexadecimal characters')

    branch_count, topology_digest = topology_observation()
    diff_raw = run('git', 'diff', '--name-status', '--find-renames', f'{base}...{head}')
    diff_digest = hashlib.sha256((diff_raw + '\n').encode('utf-8')).hexdigest()
    receipt_digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()

    evidence = {
        'status': 'ADMISSIBLE_FOR_FURTHER_REVIEW',
        'policy_id': policy['policy_id'],
        'base_sha': base,
        'head_sha': head,
        'merge_base': merge_base,
        'provider_receipt_path': str(receipt_path),
        'provider_receipt_sha256': receipt_digest,
        'provider': provider,
        'model': model,
        'session_id': session_id,
        'session_id_status': session_id_status,
        'changed_path_count': len(changed_paths),
        'deleted_path_count': len(deleted_paths),
        'renamed_source_count': len(renamed_sources),
        'critical_path_count': len(critical_paths),
        'critical_paths': critical_paths,
        'high_risk': high_risk,
        'branch_count_observed': branch_count,
        'topology_digest_sha256': topology_digest,
        'diff_name_status_sha256': diff_digest,
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
