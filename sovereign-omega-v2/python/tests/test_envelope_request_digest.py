"""
SOVEREIGN OMEGA — Collaboration request_digest field-coverage test (CLM-004)
EPISTEMIC TIER: T0 (digest sensitivity) / T2 (envelope schema)

Pins the CLM-004 property: on the live collaboration path, the canonical
envelope's request_digest covers the COMPLETE validated CollaborationRequest
(objective, mode, live, generation, autonomous, max_agents, memory_context),
so two requests differing only in an execution-affecting field produce
different digests.

Two mechanical checks, no heavy import of bridge.py (it instantiates hardware
and seeds the chain at import time):

  1. Property check — build the 7-field request dict and assert that flipping
     any single field changes payload_digest(); identical requests are stable
     across three runs.
  2. Source-pin check — read bridge.py and extract the exact key set passed to
     the collaboration request_digest payload_digest() call. This FAILS if
     someone shrinks the hashed field set back to a subset (e.g.
     objective/mode/generation), which is exactly the CLM-004 regression the
     ledger's fails_if names.

Run: python python/tests/test_envelope_request_digest.py
"""
import os
import re
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


# The full validated CollaborationRequest field set the live path hashes.
# Mirrors bridge.py:_platform_run_collaboration request_digest (bridge.py:363-371);
# the source-pin check below asserts bridge.py still hashes exactly this set.
EXPECTED_FIELDS = {
    'objective', 'mode', 'live', 'generation',
    'autonomous', 'max_agents', 'memory_context',
}

# A representative validated request. Only float-free types (str/bool/int/list),
# as canon() forbids raw floats on the hash path.
_BASE = {
    'objective': 'grow revenue',
    'mode': 'revenue',
    'live': False,
    'generation': 0,
    'autonomous': False,
    'max_agents': 5,
    'memory_context': [],
}

# One execution-affecting mutation per field. Each must change request_digest.
_MUTATIONS = {
    'objective': 'shrink costs',
    'mode': 'growth',
    'live': True,
    'generation': 1,
    'autonomous': True,
    'max_agents': 8,
    'memory_context': ['prior artifact'],
}

# ─── Property: every field is digest-affecting ────────────────────────────────

check(set(_BASE) == EXPECTED_FIELDS, 'base request carries exactly the 7 validated fields')

_base_digest = ce.payload_digest(_BASE)

# Determinism: identical requests hash identically across three runs.
_runs = {ce.payload_digest(dict(_BASE)) for _ in range(3)}
check(_runs == {_base_digest}, 'identical requests yield the same request_digest (x3)')

for _field, _new in _MUTATIONS.items():
    _variant = dict(_BASE)
    _variant[_field] = _new
    _variant_digest = ce.payload_digest(_variant)
    check(
        _variant_digest != _base_digest,
        f'flipping "{_field}" changes request_digest',
        f'digest unchanged when only "{_field}" differs — field is not covered',
    )

# ─── Source-pin: bridge.py hashes exactly the 7-field set ─────────────────────
# Reproduces how bridge.py builds the collaboration request_digest and asserts
# the hashed key set has not been shrunk. This is the mechanical guard that makes
# CLM-004 independently reproducible: it fails the instant the field set regresses.

_BRIDGE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bridge.py')
with open(_BRIDGE, encoding='utf-8') as _f:
    _SRC = _f.read()

# The collaboration site is the only `payload_digest({` (brace directly after the
# paren); the governed /claude path uses `payload_digest(` on its own line.
_MARKER = 'request_digest=_canon_env.payload_digest({'
check(_SRC.count(_MARKER) == 1, 'exactly one collaboration request_digest site in bridge.py')

_after = _SRC[_SRC.index(_MARKER) + len(_MARKER):]
_block = _after[:_after.index('})')]
_hashed_fields = set(re.findall(r"'(\w+)'\s*:", _block))
check(
    _hashed_fields == EXPECTED_FIELDS,
    'bridge.py collaboration request_digest hashes exactly the 7 validated fields',
    f'got {sorted(_hashed_fields)}, expected {sorted(EXPECTED_FIELDS)}',
)

# ─── Verdict ──────────────────────────────────────────────────────────────────

print(f'\n{PASS} passed, {FAIL} failed')
sys.exit(1 if FAIL else 0)
