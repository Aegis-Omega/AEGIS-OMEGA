"""
SOVEREIGN OMEGA — Canonical Execution Envelope (Provenance Phase 1)
EPISTEMIC TIER: T0 (canonicalization) / T2 (envelope schema)

Float-free, hash-chained provenance envelope for governed inference calls.
Design decision record: docs/adr/0001-envelope-float-encoding.md.

canon() is byte-compatible with the TypeScript T0 path
(src/core/canonicalize.ts → canonicalizeJCS) for float-free input —
the TS path applies no Unicode normalization, so this path must not either,
or decomposed input would digest differently across languages —
enforced by the cross-language digest gate:
  test/vectors/canon-vectors.json
  test/unit/canon-equivalence.test.ts
  python/tests/test_canon_equivalence.py

No wall-clock timestamps in any hashed body — sequence numbers only
(repo invariant: no time.time() in determinism-critical paths).

Dependency-free: stdlib only (hashlib, json, threading).
"""
from __future__ import annotations

import hashlib
import json
import threading

CANON_VERSION = 'JCS-1'
GENESIS = '0' * 64


def canon(value) -> bytes:
    """RFC 8785-style canonical bytes: sorted keys, no whitespace, UTF-8.
    Rejects float — integers and strings only in hashed state, exactly as
    the runtime forbids float in hash inputs (a non-determinism source).

    No Unicode normalization: the TypeScript T0 path (canonicalizeJCS) does
    not normalize, so applying NFC here would make decomposed input digest
    differently across the two languages. Byte parity with the TS path is
    asserted by python/tests/test_canon_equivalence.py (via the shared
    test/vectors/canon-vectors.json digests). This intentionally diverges
    from verifiable/chain.py::canon, which still applies NFC."""
    def check(v):
        if isinstance(v, float):
            raise TypeError("float in hashed state is forbidden (non-deterministic)")
        if isinstance(v, dict):
            for k in v:
                check(v[k])
        elif isinstance(v, (list, tuple)):
            for x in v:
                check(x)
    check(value)
    s = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def encode_floats(obj):
    """Float-elimination transform (ADR 0001): recursively convert every float
    to its shortest round-trip decimal string via repr(). Digest inputs pass
    through this transform before canon(), so payloads that legitimately carry
    floats (model outputs, projections) hash deterministically without ever
    putting a binary float on the hash path."""
    if isinstance(obj, float):
        return repr(obj)
    if isinstance(obj, dict):
        return {k: encode_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [encode_floats(x) for x in obj]
    return obj


def payload_digest(payload) -> str:
    """SHA-256 hex of canon(encode_floats(payload)) — the only permitted way to
    digest request/response payloads for the execution envelope."""
    return sha256_hex(canon(encode_floats(payload)))


class EnvelopeChain:
    """Per-process hash chain of execution envelopes. prev_hash links envelope
    N to envelope N-1; genesis prev_hash = GENESIS (64 zeros). seq is a
    monotonic per-process counter — never a timestamp.

    Body field `epistemic_tier` is the epistemic T-tier of the call ('T1'/'T2')
    — deliberately NOT named `tier`, which on the platform surface means the
    customer plan (explorer/operator/sovereign)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._seq = 0
        self._prev_hash = GENESIS

    def emit(self, request_digest: str, response_digest: str,
             model_id: str, epistemic_tier: str, provider: str) -> dict:
        with self._lock:
            body = {
                'canon_version': CANON_VERSION,
                'seq': self._seq,
                'prev_hash': self._prev_hash,
                'request_digest': request_digest,
                'response_digest': response_digest,
                'model_id': model_id,
                'epistemic_tier': epistemic_tier,
                'provider': provider,
            }
            envelope_hash = sha256_hex(canon(body))
            self._seq += 1
            self._prev_hash = envelope_hash
            envelope = dict(body)
            envelope['envelope_hash'] = envelope_hash
            envelope['signature'] = None  # Phase 2: KMS Ed25519 over envelope_hash
            return envelope


_chain = EnvelopeChain()


def emit_envelope(request_digest: str, response_digest: str,
                  model_id: str, epistemic_tier: str, provider: str) -> dict:
    """Emit the next envelope on the process-global chain."""
    return _chain.emit(request_digest, response_digest, model_id,
                       epistemic_tier, provider)
