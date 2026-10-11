"""AEGIS UWP-13 collector-origin MAC (local trust boundary, not website truth).

Only a protected collector process should hold the signing key. An untrusted
packet must never supply its own verification key or choose a trusted key ID.
This is intentionally NOT SLSA or third-party publisher authentication.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from pathlib import Path

SCHEME = 'aegis.capture.hmac-sha256.v2'
DOMAIN = b'AEGIS-UWP13-CAPTURE-BOUND-V2\x00'
KEY_ID_RE = re.compile(r'^[a-z][a-z0-9_.-]{0,63}$')
HEX64 = re.compile(r'^[a-f0-9]{64}$')
GIT_OID = re.compile(r'^(?:[a-f0-9]{40}|[a-f0-9]{64})$')
SOURCE_ID = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,63}$')
BINDING_FIELDS = frozenset({'task_id', 'repo_head', 'source_id'})
SNAPSHOT_FIELDS = frozenset({
    'schema','url','hostname','resolved_ip','captured_at','http_status',
    'content_type','tls_peer_cert_sha256','full_body_sha256',
    'excerpt_sha256','excerpt','full_bytes','truncated',
    'publisher_identity','claim_truth','authority_effect',
})

class AttestationError(ValueError):
    pass


def _binding(binding: object) -> dict:
    if type(binding) is not dict or set(binding) != BINDING_FIELDS:
        raise AttestationError('CAPTURE_BINDING_REQUIRED')
    if (type(binding['task_id']) is not str or
            not SOURCE_ID.fullmatch(binding['task_id']) or
            type(binding['source_id']) is not str or
            not SOURCE_ID.fullmatch(binding['source_id']) or
            type(binding['repo_head']) is not str or
            not GIT_OID.fullmatch(binding['repo_head'])):
        raise AttestationError('INVALID_CAPTURE_BINDING')
    return binding


def _payload(snapshot: dict, binding: dict) -> bytes:
    if type(snapshot) is not dict or set(snapshot) != SNAPSHOT_FIELDS:
        raise AttestationError('CAPTURE_FIELDS_MISMATCH')
    if snapshot.get('schema') != 'aegis.research.capture.v1':
        raise AttestationError('CAPTURE_SCHEMA_MISMATCH')
    _binding(binding)
    try:
        return DOMAIN + json.dumps({'snapshot': snapshot, 'binding': binding},
                                   sort_keys=True, separators=(',', ':'),
                                   ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as exc:
        raise AttestationError('CAPTURE_NONCANONICAL') from exc


def _validate_key(key: bytes, key_id: str) -> None:
    if type(key) is not bytes or len(key) != 32 or not isinstance(key_id, str) or not KEY_ID_RE.fullmatch(key_id):
        raise AttestationError('INVALID_TRUST_KEY')


def sign_capture(snapshot: dict, key: bytes, key_id: str, *, binding: dict | None = None) -> dict:
    """Trusted runner only: sign an unmodified, post-TLS capture record."""
    _validate_key(key, key_id)
    msg = _payload(snapshot, binding)
    mac = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return {**snapshot, 'attestation': {'scheme': SCHEME, 'key_id': key_id,
                                        'binding': dict(binding), 'mac_sha256': mac}}


def verify_capture(receipt: object, trusted_keys: dict[str, bytes] | None,
                   *, expected_binding: dict | None = None) -> bool:
    """False when absent/untrusted; tampered attestation is never a valid quorum member."""
    if type(receipt) is not dict or set(receipt) != (SNAPSHOT_FIELDS | {'attestation'}):
        return False
    a = receipt.get('attestation')
    if (type(a) is not dict or set(a) != {'scheme', 'key_id', 'mac_sha256', 'binding'} or
            a['scheme'] != SCHEME or type(a['key_id']) is not str or
            not KEY_ID_RE.fullmatch(a['key_id']) or type(a['mac_sha256']) is not str or
            not HEX64.fullmatch(a['mac_sha256'])):
        return False
    if type(trusted_keys) is not dict or a['key_id'] not in trusted_keys:
        return False
    key = trusted_keys[a['key_id']]
    try:
        # Verifier-supplied expected identity MUST match the signed binding.
        # Do not validate a request against a self-declared bound task alone.
        _binding(expected_binding)
        _binding(a['binding'])
        if a['binding'] != expected_binding:
            return False
        _validate_key(key, a['key_id'])
        expected = hmac.new(key, _payload({k: receipt[k] for k in SNAPSHOT_FIELDS},
                                          a['binding']), hashlib.sha256).hexdigest()
    except (AttestationError, KeyError):
        return False
    return hmac.compare_digest(expected, a['mac_sha256'])


def read_protected_key(path: str) -> bytes:
    """Fail closed if the key path is a symlink, not owner-only, or not owned by caller."""
    flags = os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
                (stat.S_IMODE(st.st_mode) & 0o077) or st.st_size != 32 or
                Path(path).is_symlink()):
            raise AttestationError('INSECURE_TRUST_KEY_FILE')
        key = os.read(fd, 33)
        if len(key) != 32:
            raise AttestationError('INVALID_TRUST_KEY')
        return key
    finally:
        os.close(fd)
