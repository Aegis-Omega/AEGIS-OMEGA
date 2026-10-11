"""Verifier-issued one-use nonce for research-source admission (local candidate).

A fresh challenge proves only that its KEY HOLDER endorsed a specific signed
record after the challenge existed, not that network capture occurred then.
Uses the existing owner-protected SQLite ledger and never grants tool authority.
"""
from __future__ import annotations

from contextlib import closing
import datetime as dt
import hashlib
import hmac
import json
import secrets
import sqlite3

from research_admission import AdmissionDenied, _protected_path
from research_attestation import _validate_key, verify_capture, GIT_OID
from research_intelligence import evaluate, ident, canonical, digest, timestamp

SCHEMA = 'aegis.research.challenge.v1'
RESPONSE_SCHEME = 'aegis.research.challenge.response.hmac-sha256.v1'
DOMAIN = b'AEGIS-UWP13-CHALLENGE-ENDORSEMENT-V1\0'
MAX_TTL_SECONDS = 300


def _clock(now):
    value = now if now is not None else dt.datetime.now(dt.timezone.utc)
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        raise AdmissionDenied('TRUSTED_CLOCK_REQUIRED')
    return value.astimezone(dt.timezone.utc).replace(microsecond=0)


def _identities(task_id, repo_head, source_ids):
    task_id = ident(task_id)
    if type(repo_head) is not str or not GIT_OID.fullmatch(repo_head):
        raise AdmissionDenied('INVALID_REPO_HEAD')
    if type(source_ids) not in (list, tuple) or not (2 <= len(source_ids) <= 30):
        raise AdmissionDenied('INVALID_CHALLENGE_SOURCE_SET')
    ids = [ident(x) for x in source_ids]
    if len(set(ids)) != len(ids):
        raise AdmissionDenied('DUPLICATE_CHALLENGE_SOURCE')
    return task_id, repo_head, tuple(sorted(ids))


def _connect(ledger):
    connection = sqlite3.connect(ledger, timeout=8, isolation_level=None)
    connection.execute('PRAGMA busy_timeout=8000')
    connection.execute('PRAGMA synchronous=EXTRA')
    return connection


def issue_challenge(*, ledger_path, task_id, repo_head, source_ids,
                    verified_now=None, ttl_seconds=120):
    """Trusted issuer only. No task text or untrusted packet authorizes issuance."""
    task_id, repo_head, ids = _identities(task_id, repo_head, source_ids)
    if type(ttl_seconds) is not int or not (1 <= ttl_seconds <= MAX_TTL_SECONDS):
        raise AdmissionDenied('INVALID_CHALLENGE_TTL')
    now = _clock(verified_now)
    expires = now + dt.timedelta(seconds=ttl_seconds)
    nonce = secrets.token_hex(32)  # CSPRNG 256-bit unpredictable challenge.
    nonce_hash = hashlib.sha256(bytes.fromhex(nonce)).hexdigest()
    ledger = _protected_path(ledger_path)
    try:
        with closing(_connect(ledger)) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('CREATE TABLE IF NOT EXISTS issued_challenges ('
                           'nonce_sha256 TEXT PRIMARY KEY, task_id TEXT NOT NULL, '
                           'repo_head TEXT NOT NULL, source_ids_json TEXT NOT NULL, '
                           'issued_at TEXT NOT NULL, expires_at TEXT NOT NULL, '
                           'consumed_at TEXT)')
                db.execute('INSERT INTO issued_challenges '
                           '(nonce_sha256, task_id, repo_head, source_ids_json, issued_at, expires_at) '
                           'VALUES (?, ?, ?, ?, ?, ?)',
                           (nonce_hash, task_id, repo_head, json.dumps(ids),
                            now.isoformat(), expires.isoformat()))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
    except (sqlite3.Error, OSError) as error:
        raise AdmissionDenied('CHALLENGE_LEDGER_UNAVAILABLE') from error
    return {'schema': SCHEMA, 'task_id': task_id, 'repo_head': repo_head,
            'source_ids': list(ids), 'challenge_nonce': nonce,
            'issued_at': now.isoformat(), 'expires_at': expires.isoformat(),
            'authority_effect': 'NONE'}


def _response_message(receipt, challenge, source_id, key_id):
    # No self-reported identity from the capture controls the expected task.
    return DOMAIN + canonical({'schema': RESPONSE_SCHEME,
                               'task_id': challenge['task_id'],
                               'repo_head': challenge['repo_head'],
                               'source_id': source_id,
                               'nonce': challenge['challenge_nonce'],
                               'capture_sha256': digest(canonical(receipt)),
                               'key_id': key_id})


def endorse_capture(receipt, *, challenge, source_id, key_id, signing_key):
    """Trusted collector response. A MAC alone never attests that GET occurred."""
    _validate_key(signing_key, key_id)
    source_id = ident(source_id)
    if type(challenge) is not dict or challenge.get('schema') != SCHEMA:
        raise AdmissionDenied('INVALID_CHALLENGE')
    task, head, ids = _identities(challenge.get('task_id'), challenge.get('repo_head'),
                                  challenge.get('source_ids'))
    if (source_id not in ids or type(challenge.get('challenge_nonce')) is not str or
            len(challenge['challenge_nonce']) != 64):
        raise AdmissionDenied('INVALID_CHALLENGE_BINDING')
    try:
        bytes.fromhex(challenge['challenge_nonce'])
    except ValueError as exc:
        raise AdmissionDenied('INVALID_CHALLENGE_NONCE') from exc
    if not verify_capture(receipt, {key_id: signing_key},
                          expected_binding={'task_id': task, 'repo_head': head,
                                            'source_id': source_id}):
        raise AdmissionDenied('UNVERIFIED_SOURCE_CAPTURE')
    mac = hmac.new(signing_key, _response_message(receipt, challenge, source_id, key_id),
                   hashlib.sha256).hexdigest()
    return {'scheme': RESPONSE_SCHEME, 'source_id': source_id, 'key_id': key_id,
            'mac_sha256': mac}


def admit_challenged_once(packet, *, challenge, endorsements, trusted_keys,
                          ledger_path, verified_now=None):
    """Verify issued nonce and all captures, then consume nonce + captures atomically."""
    if type(trusted_keys) is not dict or not trusted_keys:
        raise AdmissionDenied('TRUST_ROOT_REQUIRED')
    now = _clock(verified_now)
    observed = evaluate(packet, trusted_keys=trusted_keys, verified_now=now)
    if not all(p['status'] == 'READY_FOR_INDEPENDENT_TEST' for p in observed['proposals']):
        raise AdmissionDenied('NOT_ALL_PROPOSALS_TEST_READY')
    task, head = observed['task_id'], observed['repo_head']
    source_ids = {sid for p in packet['proposals'] for sid in p['source_ids']}
    if type(challenge) is not dict or challenge.get('schema') != SCHEMA:
        raise AdmissionDenied('INVALID_CHALLENGE')
    ch_task, ch_head, ch_ids = _identities(challenge.get('task_id'),
                                          challenge.get('repo_head'), challenge.get('source_ids'))
    if (task != ch_task or head != ch_head or source_ids != set(ch_ids) or
            type(endorsements) is not dict or set(endorsements) != source_ids):
        raise AdmissionDenied('CHALLENGE_BINDING_MISMATCH')
    nonce = challenge.get('challenge_nonce')
    if type(nonce) is not str or len(nonce) != 64:
        raise AdmissionDenied('INVALID_CHALLENGE_NONCE')
    try:
        nonce_raw = bytes.fromhex(nonce)
    except ValueError as exc:
        raise AdmissionDenied('INVALID_CHALLENGE_NONCE') from exc
    nonce_hash = hashlib.sha256(nonce_raw).hexdigest()
    ledger = _protected_path(ledger_path)
    packet_sha = observed['packet_sha256']
    src = {s['id']: s for s in packet['sources']}
    try:
        with closing(_connect(ledger)) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                # Challenges can only be created with issue_challenge on this same ledger.
                row = db.execute('SELECT task_id, repo_head, source_ids_json, issued_at, '
                                 'expires_at, consumed_at FROM issued_challenges '
                                 'WHERE nonce_sha256 = ?', (nonce_hash,)).fetchone()
                if row is None:
                    raise AdmissionDenied('UNKNOWN_VERIFIER_CHALLENGE')
                record_task, record_head, record_ids, start, expiry, used = row
                started, expires = dt.datetime.fromisoformat(start), dt.datetime.fromisoformat(expiry)
                if (record_task != task or record_head != head or
                        json.loads(record_ids) != list(ch_ids) or
                        start != challenge.get('issued_at') or expiry != challenge.get('expires_at')):
                    raise AdmissionDenied('CHALLENGE_LEDGER_MISMATCH')
                if used is not None:
                    raise AdmissionDenied('CHALLENGE_ALREADY_CONSUMED')
                if not started <= now <= expires:
                    raise AdmissionDenied('CHALLENGE_EXPIRED_OR_NOT_STARTED')
                claims = []
                for sid in ch_ids:
                    item = src[sid]
                    receipt = item.get('capture_receipt')
                    if not verify_capture(receipt, trusted_keys,
                                      expected_binding={'task_id': task, 'repo_head': head,
                                                        'source_id': sid}):
                        raise AdmissionDenied('SOURCE_MAC_REJECTED')
                    captured = timestamp(item['captured_at'])
                    if not started <= captured <= now:
                        raise AdmissionDenied('CAPTURE_PREDATES_CHALLENGE')
                    endorsement = endorsements[sid]
                    if (type(endorsement) is not dict or
                            set(endorsement) != {'scheme', 'source_id', 'key_id', 'mac_sha256'} or
                            endorsement['scheme'] != RESPONSE_SCHEME or
                            endorsement['source_id'] != sid or
                            type(endorsement['mac_sha256']) is not str or
                            len(endorsement['mac_sha256']) != 64):
                        raise AdmissionDenied('INVALID_CHALLENGE_ENDORSEMENT')
                    key_id = endorsement['key_id']
                    if (type(key_id) is not str or key_id not in trusted_keys or
                            receipt['attestation']['key_id'] != key_id):
                        raise AdmissionDenied('UNTRUSTED_ENDORSER')
                    key = trusted_keys[key_id]
                    _validate_key(key, key_id)
                    expected = hmac.new(key, _response_message(receipt, challenge, sid, key_id),
                                        hashlib.sha256).hexdigest()
                    if not hmac.compare_digest(expected, endorsement['mac_sha256']):
                        raise AdmissionDenied('CHALLENGE_RESPONSE_MAC_MISMATCH')
                    claims.append((digest(canonical(receipt)), item['captured_at']))
                db.execute('CREATE TABLE IF NOT EXISTS consumed ('
                           'evidence_id TEXT PRIMARY KEY, packet_sha256 TEXT NOT NULL, '
                           'task_id TEXT NOT NULL, repo_head TEXT NOT NULL, '
                           'captured_at TEXT NOT NULL, consumed_at TEXT NOT NULL)')
                consumed_at = now.isoformat()
                for evidence_id, captured_at in claims:
                    db.execute('INSERT INTO consumed VALUES (?, ?, ?, ?, ?, ?)',
                               (evidence_id, packet_sha, task, head, captured_at, consumed_at))
                db.execute('UPDATE issued_challenges SET consumed_at = ? WHERE nonce_sha256 = ? '
                           'AND consumed_at IS NULL', (consumed_at, nonce_hash))
                if db.execute('SELECT changes()').fetchone()[0] != 1:
                    raise AdmissionDenied('CHALLENGE_ALREADY_CONSUMED')
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
    except sqlite3.IntegrityError as error:
        raise AdmissionDenied('EVIDENCE_ALREADY_CONSUMED') from error
    except (sqlite3.Error, OSError) as error:
        raise AdmissionDenied('CHALLENGE_LEDGER_UNAVAILABLE') from error
    result = {'schema': 'aegis.research.challenged_admission.v1',
              'status': 'CHALLENGE_CONSUMED_FOR_INDEPENDENT_TEST',
              'task_id': task, 'repo_head': head, 'packet_sha256': packet_sha,
              'challenge_nonce_sha256': nonce_hash, 'verified_capture_count': len(claims),
              'authority_effect': 'NONE', 'actual_execution': 'NOT_INDEPENDENTLY_OBSERVED',
              'source_truth': 'NOT_VERIFIED', 'publisher_identity': 'NOT_INDEPENDENTLY_AUTHENTICATED'}
    result['receipt_sha256'] = digest(canonical(result))
    return result
