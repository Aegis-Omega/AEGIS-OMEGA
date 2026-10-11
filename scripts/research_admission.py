#!/usr/bin/env python3
"""One-shot LOCAL research-evidence admission gate with crash-atomic SQLite journal.

Requires separately verified HMAC captures, a protected persistent directory, and
an explicit write opt-in. A signature is NOT proof a network request occurred.
This module is NOT a production authorization or operator-approval mechanism.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

from research_intelligence import (evaluate, parse_json, canonical, digest,
                                   ident, timestamp, ResearchError, MAX_AGE_DAYS)
from research_attestation import verify_capture, read_protected_key

SCHEMA = 'aegis.research.one_shot_admission.v1'


class AdmissionDenied(ValueError):
    pass


def _protected_path(path: str) -> str:
    """Require an owner-only existing parent and owner-only non-symlink DB file."""
    if type(path) is not str or not path.startswith('/') or not path.endswith('.sqlite3'):
        raise AdmissionDenied('UNTRUSTED_LEDGER_PATH')
    parent = Path(path).parent
    st = os.lstat(parent)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) & 0o077:
        raise AdmissionDenied('UNTRUSTED_LEDGER_PARENT')
    flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
    try:
        fd = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        fd = os.open(path, flags)
    try:
        fs = os.fstat(fd)
        if (not stat.S_ISREG(fs.st_mode) or fs.st_uid != os.geteuid() or
                stat.S_IMODE(fs.st_mode) & 0o077):
            raise AdmissionDenied('UNTRUSTED_LEDGER_FILE')
    finally:
        os.close(fd)
    return path


def _insert_claims(connection: sqlite3.Connection, entries: list[tuple], packet_sha: str,
                   task: str, head: str, consumed_at: str):
    for evidence_id, captured_at in entries:
        connection.execute('INSERT INTO consumed (evidence_id, packet_sha256, task_id, repo_head, captured_at, consumed_at) '
                           'VALUES (?, ?, ?, ?, ?, ?)',
                           (evidence_id, packet_sha, task, head, captured_at, consumed_at))


def admit_once(packet: dict, *, trusted_keys: dict[str, bytes],
               ledger_path: str, verified_now: dt.datetime | None = None) -> dict:
    """Admit an all-ready packet at most once for each unique signed capture.

    A repeated use of ANY consumed qualifying capture rejects the entire packet.
    Multiple proposals within one packet may cite the same capture without
    consuming it more than once. Every DB insertion is in one transaction.
    """
    if type(trusted_keys) is not dict or not trusted_keys:
        raise AdmissionDenied('TRUST_ROOT_REQUIRED')
    now = verified_now if verified_now is not None else dt.datetime.now(dt.timezone.utc)
    if not isinstance(now, dt.datetime) or now.tzinfo is None:
        raise AdmissionDenied('TRUSTED_CLOCK_REQUIRED')
    now = now.astimezone(dt.timezone.utc)
    observed = evaluate(packet, trusted_keys=trusted_keys, verified_now=now)
    if not all(p['status'] == 'READY_FOR_INDEPENDENT_TEST' for p in observed['proposals']):
        raise AdmissionDenied('NOT_ALL_PROPOSALS_TEST_READY')
    task, head = observed['task_id'], observed['repo_head']
    ids = {sid for proposal in packet['proposals'] for sid in proposal['source_ids']}
    sources = {s['id']: s for s in packet['sources']}
    claims: dict[str, str] = {}
    for sid in sorted(ids):
        src = sources[sid]
        receipt = src.get('capture_receipt')
        if src['acquisition'] != 'connector_capture' or not verify_capture(
            receipt, trusted_keys,
            expected_binding={'task_id': task, 'repo_head': head, 'source_id': sid}):
            continue
        age = (now - timestamp(src['captured_at'])).total_seconds()
        if not 0 <= age <= MAX_AGE_DAYS * 86400:
            continue
        if (receipt['url'] != src['url'] or receipt['excerpt'] != src['content'] or
                receipt['excerpt_sha256'] != src['sha256'] or
                receipt['captured_at'] != src['captured_at']):
            continue
        receipt_id = hashlib.sha256(canonical(receipt)).hexdigest()
        claims[receipt_id] = src['captured_at']
    if len(claims) < 2:
        raise AdmissionDenied('INSUFFICIENT_VERIFIED_CAPTURES')

    ledger = _protected_path(ledger_path)
    packet_sha = observed['packet_sha256']
    consumed_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    entries = sorted(claims.items())
    try:
        with closing(sqlite3.connect(ledger, timeout=8, isolation_level=None)) as connection:
            connection.execute('PRAGMA busy_timeout=8000')
            connection.execute('PRAGMA synchronous=EXTRA')
            connection.execute('BEGIN IMMEDIATE')
            try:
                connection.execute('CREATE TABLE IF NOT EXISTS consumed ('
                                   'evidence_id TEXT PRIMARY KEY, '
                                   'packet_sha256 TEXT NOT NULL, '
                                   'task_id TEXT NOT NULL, repo_head TEXT NOT NULL, '
                                   'captured_at TEXT NOT NULL, consumed_at TEXT NOT NULL)')
                _insert_claims(connection, entries, packet_sha, task, head, consumed_at)
                connection.execute('COMMIT')
            except BaseException:
                connection.execute('ROLLBACK')
                raise
    except sqlite3.IntegrityError as exc:
        raise AdmissionDenied('EVIDENCE_ALREADY_CONSUMED') from exc
    except (sqlite3.Error, OSError) as exc:
        raise AdmissionDenied('LEDGER_UNAVAILABLE') from exc

    result = {'schema': SCHEMA, 'status': 'ADMITTED_ONCE_FOR_INDEPENDENT_TEST',
              'task_id': task, 'repo_head': head, 'packet_sha256': packet_sha,
              'verified_capture_count': len(entries),
              'consumed_at': consumed_at, 'source_truth': 'NOT_VERIFIED',
              'publisher_identity': 'NOT_INDEPENDENTLY_AUTHENTICATED',
              'actual_execution': 'NOT_INDEPENDENTLY_OBSERVED',
              'operator_authority': 'NOT_GRANTED', 'deployment_authority': 'NONE'}
    result['receipt_sha256'] = digest(canonical(result))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Explicit one-shot LOCAL receipt admission')
    parser.add_argument('packet', help='Research packet JSON; no HTTP performed')
    parser.add_argument('--trusted-key-file', required=True)
    parser.add_argument('--trusted-key-id', required=True)
    parser.add_argument('--ledger', required=True, help='Owner-only absolute .sqlite3 in owner-only directory')
    parser.add_argument('--allow-ledger-write', action='store_true', help='Explicit local mutation opt-in')
    args = parser.parse_args(argv)
    if not args.allow_ledger_write:
        parser.error('LEDGER_WRITE_NOT_AUTHORIZED')
    try:
        result = admit_once(parse_json(Path(args.packet).read_text(encoding='utf-8')),
                            trusted_keys={ident(args.trusted_key_id).lower():
                                          read_protected_key(args.trusted_key_file)},
                            ledger_path=args.ledger)
    except (AdmissionDenied, ResearchError, OSError, ValueError) as error:
        print(json.dumps({'status':'REJECTED', 'reason':str(error),
                          'deployment_authority':'NONE'}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
