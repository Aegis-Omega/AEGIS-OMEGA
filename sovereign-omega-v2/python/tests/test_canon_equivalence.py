"""
SOVEREIGN OMEGA — Canonical Envelope + Cross-Language Digest Tests
EPISTEMIC TIER: T0 (digest vectors) / T2 (envelope schema)

Covers canonical_envelope.py (Provenance Phase 1):
  - Shared digest vectors (test/vectors/canon-vectors.json) — same digests the
    TypeScript T0 path produces (test/unit/canon-equivalence.test.ts)
  - Byte parity with the canonicalization source of truth, verifiable/chain.py
  - encode_floats() transform (ADR 0001)
  - ExecutionEnvelope chain: seq monotonic, prev_hash linkage, genesis,
    float rejection without the transform

Run: python python/tests/test_canon_equivalence.py
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import canonical_envelope as ce

PASS = 0
FAIL = 0


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f'  PASS  {name}')


def fail(name: str, detail: str = '') -> None:
    global FAIL
    FAIL += 1
    print(f'  FAIL  {name}  {detail}')


def check(cond: bool, name: str, detail: str = '') -> None:
    ok(name) if cond else fail(name, detail)


# ─── Cross-language digest vectors ────────────────────────────────────────────

_VECTORS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'test', 'vectors', 'canon-vectors.json',
)

with open(_VECTORS_PATH, encoding='utf-8') as f:
    _VECTORS = json.load(f)['vectors']

check(len(_VECTORS) >= 10, f'vector file has >=10 cases ({len(_VECTORS)})')

for vec in _VECTORS:
    got = ce.payload_digest(vec['input'])
    check(
        got == vec['sha256'],
        f'vector digest: {vec["name"]}',
        f'expected {vec["sha256"]} got {got}',
    )

# Determinism: same input, byte-identical canonical output, three runs
for vec in _VECTORS[:3]:
    runs = {ce.canon(vec['input']) for _ in range(3)}
    check(len(runs) == 1, f'canon deterministic x3: {vec["name"]}')

# ─── Byte parity with verifiable/chain.py (source of truth) ───────────────────

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, _REPO_ROOT)
try:
    from verifiable.chain import canon as chain_canon
except ImportError:
    chain_canon = None

if chain_canon is None:
    fail('verifiable/chain.py importable for parity check')
else:
    for vec in _VECTORS:
        check(
            ce.canon(vec['input']) == chain_canon(vec['input']),
            f'canon byte parity with verifiable/chain.py: {vec["name"]}',
        )
    check(ce.GENESIS == '0' * 64, 'GENESIS matches chain.py convention (64 zeros)')

# ─── encode_floats transform (ADR 0001) ───────────────────────────────────────

check(ce.encode_floats(0.1) == '0.1', 'encode_floats: shortest round-trip repr')
check(ce.encode_floats(1.0) == '1.0', 'encode_floats: 1.0 -> "1.0"')
check(
    ce.encode_floats({'a': [0.5, 2, 'x'], 'b': {'c': 0.25}})
    == {'a': ['0.5', 2, 'x'], 'b': {'c': '0.25'}},
    'encode_floats: recursive over dict/list, non-floats untouched',
)
check(ce.encode_floats(7) == 7, 'encode_floats: int passes through')
check(ce.encode_floats(True) is True, 'encode_floats: bool passes through (not a float)')

try:
    ce.canon({'x': 0.5})
    fail('canon rejects raw float')
except TypeError:
    ok('canon rejects raw float')

check(
    ce.payload_digest({'x': 0.5}) == ce.payload_digest({'x': '0.5'}),
    'payload_digest: float digested as its decimal string (documented non-injectivity)',
)

# ─── ExecutionEnvelope chain ──────────────────────────────────────────────────

chain = ce.EnvelopeChain()
e0 = chain.emit('a' * 64, 'b' * 64, 'model-x', 'T1', 'anthropic')
e1 = chain.emit('c' * 64, 'd' * 64, 'model-x', 'T1', 'anthropic')
e2 = chain.emit('e' * 64, 'f' * 64, 'model-y', 'T2', 'demo')

check(e0['seq'] == 0 and e1['seq'] == 1 and e2['seq'] == 2, 'seq monotonic from 0')
check(e0['prev_hash'] == ce.GENESIS, 'genesis prev_hash is 64 zeros')
check(e1['prev_hash'] == e0['envelope_hash'], 'prev_hash links envelope 1 -> 0')
check(e2['prev_hash'] == e1['envelope_hash'], 'prev_hash links envelope 2 -> 1')
check(e0['canon_version'] == 'JCS-1', 'canon_version pinned to JCS-1')
check(e0['signature'] is None, 'signature placeholder is None (Phase 2: KMS Ed25519)')

_body_keys = {
    'canon_version', 'seq', 'prev_hash', 'request_digest', 'response_digest',
    'model_id', 'tier', 'provider',
}
check(
    set(e0.keys()) == _body_keys | {'envelope_hash', 'signature'},
    'envelope has exactly the Phase 1 fields',
)

# envelope_hash is recomputable: sha256(canon(body)) over the 8 body fields
_body = {k: e1[k] for k in _body_keys}
_recomputed = hashlib.sha256(ce.canon(_body)).hexdigest()
check(_recomputed == e1['envelope_hash'], 'envelope_hash recomputable from body via canon()')

check('ts' not in e0 and 'timestamp' not in e0, 'no wall-clock timestamp in envelope')

# ─── Verdict ──────────────────────────────────────────────────────────────────

print(f'\n{PASS} passed, {FAIL} failed')
sys.exit(1 if FAIL else 0)
