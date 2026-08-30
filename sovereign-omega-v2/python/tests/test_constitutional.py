"""
SOVEREIGN OMEGA — Constitutional File Tests
EPISTEMIC TIER: T0

Unit tests for dna.py (genome/schema), gate.py (mutation authority),
and router.py (execution router). These files are FROZEN constitutional
components — any regression here is a T0 violation.

Run: python tests/test_constitutional.py
"""
import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dna import (
    EventClass, MutationVerdict, GateSignal, EventSchema, RouteRecord,
    SCHEMAS, VERIFIER_MAP, INVARIANTS, TELEMETRY_FIELDS, VERSION, LAYER,
)
from gate import MutationGate, gate as global_gate, WINDOW_SIZE, MIN_ACCEPTANCE_RATE
from router import ExecutionRouter, router as global_router, MAX_AUDIT_TRAIL


PASS = 0
FAIL = 0


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f'  PASS  {name}')


def fail(name: str, reason: str) -> None:
    global FAIL
    FAIL += 1
    print(f'  FAIL  {name}: {reason}')


def _chk(name: str, condition: bool, reason: str = '') -> None:
    if condition:
        ok(name)
    else:
        fail(name, reason or 'assertion failed')


def expect_raises(name: str, exc_type: type, fn) -> None:
    try:
        fn()
        fail(name, f'expected {exc_type.__name__} but no exception raised')
    except exc_type:
        ok(name)
    except Exception as e:
        fail(name, f'expected {exc_type.__name__} but got {type(e).__name__}: {e}')


# ── dna.py tests ─────────────────────────────────────────────────────────────

def test_dna():
    print('\ndna.py:')

    _chk('VERSION is a semver string', isinstance(VERSION, str) and VERSION.count('.') == 2)
    _chk('LAYER is B', LAYER == 'B')

    # EventClass completeness
    classes = set(EventClass)
    _chk('EventClass has 4 members', len(classes) == 4)
    _chk('GOVERNANCE in EventClass', EventClass.GOVERNANCE in classes)
    _chk('CALIBRATION in EventClass', EventClass.CALIBRATION in classes)
    _chk('TELEMETRY in EventClass', EventClass.TELEMETRY in classes)
    _chk('EPOCH in EventClass', EventClass.EPOCH in classes)

    # MutationVerdict completeness
    verdicts = set(MutationVerdict)
    _chk('MutationVerdict has 4 members', len(verdicts) == 4)
    for v in ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED'):
        _chk(f'MutationVerdict.{v} exists', MutationVerdict[v] in verdicts)

    # SCHEMAS: one per EventClass, correct types
    _chk('SCHEMAS covers all EventClass members', set(SCHEMAS.keys()) == classes)
    for ec, schema in SCHEMAS.items():
        _chk(f'SCHEMAS[{ec.value}] is EventSchema', isinstance(schema, EventSchema))
        _chk(f'SCHEMAS[{ec.value}].payload_size_max > 0', schema.payload_size_max > 0)

    # VERIFIER_MAP: bytes 0x00–0x03 → EventClass
    _chk('VERIFIER_MAP has 4 entries', len(VERIFIER_MAP) == 4)
    _chk('0x00 → GOVERNANCE', VERIFIER_MAP.get(0x00) == EventClass.GOVERNANCE)
    _chk('0x01 → CALIBRATION', VERIFIER_MAP.get(0x01) == EventClass.CALIBRATION)
    _chk('0x02 → TELEMETRY', VERIFIER_MAP.get(0x02) == EventClass.TELEMETRY)
    _chk('0x03 → EPOCH', VERIFIER_MAP.get(0x03) == EventClass.EPOCH)
    _chk('0xFF not in VERIFIER_MAP', VERIFIER_MAP.get(0xFF) is None)

    # INVARIANTS: non-empty tuple of strings
    _chk('INVARIANTS is non-empty', len(INVARIANTS) >= 5)
    _chk('all INVARIANTS are strings', all(isinstance(i, str) for i in INVARIANTS))

    # GateSignal is frozen
    gs = GateSignal('p1', 1, True, 0.5)
    expect_raises('GateSignal is frozen', (AttributeError, TypeError), lambda: setattr(gs, 'sequence', 99))

    # RouteRecord is frozen
    rr = RouteRecord(1, EventClass.GOVERNANCE, 0x00, 64, 'ROUTED', None)
    expect_raises('RouteRecord is frozen', (AttributeError, TypeError), lambda: setattr(rr, 'sequence', 99))

    # TELEMETRY_FIELDS: required fields present
    for field in ('pgcs_disk_swap_bytes_in', 'tgcs_variance', 'afse_r2', 'epoch_state', 'sequence'):
        _chk(f'TELEMETRY_FIELDS contains {field}', field in TELEMETRY_FIELDS)


# ── gate.py tests ─────────────────────────────────────────────────────────────

def test_gate():
    print('\ngate.py:')

    # --- Basic verdict lifecycle ---
    g = MutationGate(window_size=4, min_rate=0.5)
    _chk('PENDING for unknown proposal', g.verdict('unknown') == MutationVerdict.PENDING)
    _chk('is_approved False for unknown', not g.is_approved('unknown'))
    _chk('acceptance_rate 0 with no signals', g.acceptance_rate() == 0.0)
    _chk('last_sequence -1 initially', g.last_sequence() == -1)
    _chk('total_signals 0 initially', g.total_signals() == 0)

    # --- Record accepted signals ---
    g.record_signal(GateSignal('p1', 1, True, 0.4))
    g.record_signal(GateSignal('p1', 2, True, 0.6))
    _chk('last_sequence updated to 2', g.last_sequence() == 2)
    _chk('total_signals 2 after two records', g.total_signals() == 2)
    _chk('acceptance_rate 1.0 after two accepts', g.acceptance_rate() == 1.0)
    _chk('p1 APPROVED after majority accepts', g.verdict('p1') == MutationVerdict.APPROVED)
    _chk('is_approved True for p1', g.is_approved('p1'))

    # --- Out-of-order signal discarded (but counted in total) ---
    g.record_signal(GateSignal('p1', 0, False, -0.5))
    _chk('total_signals 3 including discarded', g.total_signals() == 3)
    _chk('last_sequence still 2 after discard', g.last_sequence() == 2)
    _chk('window unchanged after discard — still 2/2', g.acceptance_rate() == 1.0)

    # --- Duplicate sequence discarded ---
    g.record_signal(GateSignal('p1', 2, False, -0.1))
    _chk('duplicate seq discarded', g.last_sequence() == 2)
    _chk('total_signals 4 including duplicate', g.total_signals() == 4)

    # --- Rejection ---
    g2 = MutationGate(window_size=4, min_rate=0.75)
    g2.record_signal(GateSignal('p2', 1, False, -0.3))
    g2.record_signal(GateSignal('p2', 2, False, -0.2))
    g2.record_signal(GateSignal('p2', 3, True, 0.1))
    _chk('p2 REJECTED when rate < min_rate', g2.verdict('p2') == MutationVerdict.REJECTED)
    _chk('is_approved False for p2', not g2.is_approved('p2'))

    # --- Window boundary ---
    g3 = MutationGate(window_size=2, min_rate=0.5)
    g3.record_signal(GateSignal('p3', 1, False, -0.5))
    g3.record_signal(GateSignal('p3', 2, False, -0.3))
    g3.record_signal(GateSignal('p3', 3, True, 0.8))   # evicts seq=1 (False)
    g3.record_signal(GateSignal('p3', 4, True, 0.9))   # evicts seq=2 (False)
    _chk('window of 2: two Trues → APPROVED', g3.verdict('p3') == MutationVerdict.APPROVED)

    # --- Seal ---
    gs = MutationGate(window_size=4, min_rate=0.5)
    gs.record_signal(GateSignal('ps', 1, True, 0.7))
    gs.seal()
    _chk('sealed gate reports is_sealed True', gs.is_sealed)
    before = gs.total_signals()
    gs.record_signal(GateSignal('ps', 2, True, 0.9))
    _chk('signal after seal not counted', gs.total_signals() == before)
    _chk('sequence not updated after seal', gs.last_sequence() == 1)

    # --- Telemetry ---
    t = g.telemetry()
    for key in ('gate_acceptance_rate', 'gate_window_size', 'gate_last_sequence', 'gate_total_signals', 'gate_sealed'):
        _chk(f'telemetry has {key}', key in t)

    # --- Default constants ---
    _chk('WINDOW_SIZE is 32', WINDOW_SIZE == 32)
    _chk('MIN_ACCEPTANCE_RATE is 0.5', MIN_ACCEPTANCE_RATE == 0.5)


# ── router.py tests ───────────────────────────────────────────────────────────

def test_router():
    print('\nrouter.py:')

    # --- Registration ---
    r = ExecutionRouter()
    _chk('not sealed initially', not r.is_sealed)
    _chk('no registered classes initially', r.registered_classes == [])

    called = {}
    def handler(ec_name):
        def h(p, v, c, s): called[ec_name] = s; return {'ec': ec_name, 's': s}
        return h

    r.register(EventClass.GOVERNANCE, handler('gov'))
    r.register(EventClass.CALIBRATION, handler('cal'))
    r.register(EventClass.TELEMETRY, handler('tel'))
    r.register(EventClass.EPOCH, handler('epo'))

    _chk('registered_classes has 4 entries', len(r.registered_classes) == 4)

    # Duplicate registration raises
    expect_raises('duplicate registration raises RuntimeError', RuntimeError,
                  lambda: r.register(EventClass.GOVERNANCE, handler('gov2')))

    # Route before seal raises
    expect_raises('route before seal raises RuntimeError', RuntimeError,
                  lambda: r.route(b'x', b'\x00', b''))

    # --- Sealing ---
    r.seal()
    _chk('sealed after seal()', r.is_sealed)
    expect_raises('register after seal raises RuntimeError', RuntimeError,
                  lambda: r.register(EventClass.GOVERNANCE, handler('late')))

    # --- Routing by verifier byte ---
    res = r.route(b'payload', b'\x00', b'context')
    _chk('0x00 routes to GOVERNANCE', res.get('ec') == 'gov')
    _chk('0x00 sequence is 0 (first route)', res.get('s') == 0)

    res = r.route(b'x', b'\x01', b'')
    _chk('0x01 routes to CALIBRATION', res.get('ec') == 'cal')
    _chk('0x01 sequence is 1', res.get('s') == 1)

    res = r.route(b'x', b'\x02', b'')
    _chk('0x02 routes to TELEMETRY', res.get('ec') == 'tel')

    res = r.route(b'x', b'\x03', b'')
    _chk('0x03 routes to EPOCH', res.get('ec') == 'epo')

    # --- Unknown verifier — fail-closed ---
    res = r.route(b'x', b'\xff', b'')
    _chk('0xFF → REJECTED', res.get('status') == 'REJECTED')
    _chk('0xFF reason is UNKNOWN_EVENT_CLASS', res.get('reason') == 'UNKNOWN_EVENT_CLASS')

    # --- Empty verifier → defaults to GOVERNANCE ---
    res = r.route(b'x', b'', b'')
    _chk('empty verifier → GOVERNANCE', res.get('ec') == 'gov')

    # --- Schema size bounds ---
    big_payload = b'x' * 70000   # exceeds GOVERNANCE payload_size_max (65536)
    res = r.route(big_payload, b'\x00', b'')
    _chk('oversized payload → REJECTED', res.get('status') == 'REJECTED')
    _chk('reason mentions PAYLOAD_EXCEEDS', 'PAYLOAD_EXCEEDS' in res.get('reason', ''))

    big_context = b'x' * 5000   # exceeds GOVERNANCE context_size_max (4096)
    res = r.route(b'ok', b'\x00', big_context)
    _chk('oversized context → REJECTED', res.get('status') == 'REJECTED')
    _chk('reason mentions CONTEXT_EXCEEDS', 'CONTEXT_EXCEEDS' in res.get('reason', ''))

    # --- Sequence monotonically increases ---
    r2 = ExecutionRouter()
    r2.register(EventClass.GOVERNANCE, lambda p, v, c, s: {'s': s})
    r2.seal()
    seqs = [r2.route(b'x', b'\x00', b'')['s'] for _ in range(5)]
    _chk('sequence monotonically increases', seqs == list(range(5)))

    # --- Audit trail ---
    trail = r.audit_trail(last_n=3)
    _chk('audit trail returns list', isinstance(trail, list))
    _chk('audit trail length ≤ 3', len(trail) <= 3)
    if trail:
        rec = trail[-1]
        for key in ('sequence', 'event_class', 'outcome'):
            _chk(f'audit record has {key}', key in rec)

    # --- Telemetry ---
    t = r.telemetry()
    for key in ('router_sealed', 'router_sequence', 'router_registered_classes',
                'router_total_events', 'router_routed', 'router_rejected'):
        _chk(f'telemetry has {key}', key in t)
    _chk('router_sealed True in telemetry', t['router_sealed'])
    _chk('router_routed > 0', t['router_routed'] > 0)

    # --- Handler error is caught, returns ERROR dict, does not raise ---
    r3 = ExecutionRouter()
    r3.register(EventClass.GOVERNANCE, lambda p, v, c, s: 1 / 0)  # always raises
    r3.seal()
    res = r3.route(b'x', b'\x00', b'')
    _chk('handler exception returns ERROR dict', res.get('status') == 'ERROR')
    _chk('error reason is populated', bool(res.get('reason')))

    # --- MAX_AUDIT_TRAIL constant ---
    _chk('MAX_AUDIT_TRAIL is 10000', MAX_AUDIT_TRAIL == 10_000)


# ── Hash verification ─────────────────────────────────────────────────────────

def test_hashes():
    print('\nhash integrity:')
    expected = {
        'gate.py':   'bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc',
        'dna.py':    'cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8',
        'router.py': '8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941',
    }
    base = os.path.dirname(os.path.dirname(__file__))
    for filename, exp_hash in expected.items():
        path = os.path.join(base, filename)
        if not os.path.exists(path):
            fail(f'{filename} hash', f'file not found at {path}')
            continue
        with open(path, 'rb') as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        _chk(f'{filename} hash matches', actual == exp_hash,
             f'expected {exp_hash[:12]}… got {actual[:12]}…')


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== CONSTITUTIONAL FILE TESTS ===')
    test_dna()
    test_gate()
    test_router()
    test_hashes()
    print(f'\n{"=" * 33}')
    print(f'PASS: {PASS}  FAIL: {FAIL}')
    if FAIL > 0:
        print('RESULT: FAIL — constitutional regression detected')
        sys.exit(1)
    print('RESULT: PASS — all constitutional files verified')
