"""Mechanical tests for the T0↔T3 bridge boundary.

Run:
  python python/tests/test_t3_research_bridge.py
"""
import copy
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import canonical_envelope as _canon_env

from t3_research_bridge import (
    build_t3_research_snapshot,
    validate_t3_candidate,
)

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


def check(condition: bool, name: str, detail: str = '') -> None:
    ok(name) if condition else fail(name, detail)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


_HEAD = 'a' * 40
_TELEMETRY = {
    'sequence': 17,
    'epoch': 3,
    'avg_vcg_error': 0.12,
    'drift_index': 0.2,
    'corruption_count': 0,
    'failsafe_state': 'NOMINAL',
    'pgcs_passes': True,
    'secret_internal_field': 'must-not-leak',
}
_GATE = {
    'gate_acceptance_rate': 0.8,
    'gate_window_size': 32,
    'gate_last_sequence': 16,
    'gate_total_signals': 17,
    'gate_sealed': False,
    'private': 'must-not-leak',
}
_ROUTER = {
    'router_total_events': 9,
    'router_rejected': 1,
    'router_sealed': True,
    'private': 'must-not-leak',
}

_SNAPSHOT = build_t3_research_snapshot(
    telemetry=_TELEMETRY,
    gate_telemetry=_GATE,
    router_telemetry=_ROUTER,
    exact_head=_HEAD,
)

_SNAPSHOT_2 = build_t3_research_snapshot(
    telemetry=_TELEMETRY,
    gate_telemetry=_GATE,
    router_telemetry=_ROUTER,
    exact_head=_HEAD,
)

check(_SNAPSHOT == _SNAPSHOT_2, 'snapshot is deterministic across identical runs')
check(_SNAPSHOT['t3_research_only'] is True, 'snapshot is marked T3 research only')
check(_SNAPSHOT['write_back_authority'] is False, 'snapshot has zero write-back authority')
check(_SNAPSHOT['authority_effect'] == 'NONE', 'snapshot authority effect is NONE')
check(
    'secret_internal_field' not in _SNAPSHOT['telemetry'],
    'snapshot uses explicit telemetry allow-list',
)
check(
    'private' not in _SNAPSHOT['gate'] and 'private' not in _SNAPSHOT['router'],
    'gate/router private fields are not exported',
)

_CONFIG = {'policy': 'bounded-v1', 'budget_units': 100}
_RESULT = {'verified_correct': True, 'score_q16': 65536}

_BASE = {
    'schema_version': '1.0.0',
    'mechanism_id': 'DSR',
    'experiment_id': 'dsr-001',
    'source_snapshot': _SNAPSHOT,
    'source_snapshot_digest': _SNAPSHOT['snapshot_digest'],
    'config': _CONFIG,
    'config_digest': _canon_env.payload_digest(_CONFIG),
    'result': _RESULT,
    'result_digest': _canon_env.payload_digest(_RESULT),
    'falsifier_status': 'SUPPORTED',
    'requested_target_tier': 'T2',
    'authority_effect': 'NONE',
    'write_back_requested': False,
}

_valid = validate_t3_candidate(_BASE, current_exact_head=_HEAD)
check(_valid['outcome'] == 'STRUCTURALLY_VALID', 'valid DSR candidate is structurally valid')
check(_valid['promotion_granted'] is False, 'structural validity never grants promotion')
check(
    _valid['next_required_gate'] == 'AEGIS_EXPERIMENT_ADMISSION',
    'valid candidate is routed to existing experiment-admission gate',
)
check(_valid['write_back_authority'] is False, 'candidate receipt has zero write-back authority')

_rar = copy.deepcopy(_BASE)
_rar['mechanism_id'] = 'RAR'
_rar['experiment_id'] = 'rar-001'
check(
    validate_t3_candidate(_rar, current_exact_head=_HEAD)['outcome']
    == 'STRUCTURALLY_VALID',
    'RAR is an admitted research mechanism identifier',
)

for field, value, reason in (
    ('write_back_requested', True, 'WRITE_BACK_FORBIDDEN'),
    ('authority_effect', 'T0', 'AUTHORITY_EFFECT_MUST_BE_NONE'),
    ('requested_target_tier', 'T0', 'DIRECT_OR_INVALID_TIER_PROMOTION'),
    ('mechanism_id', 'UNKNOWN', 'UNKNOWN_MECHANISM'),
):
    candidate = copy.deepcopy(_BASE)
    candidate[field] = value
    receipt = validate_t3_candidate(candidate, current_exact_head=_HEAD)
    check(
        receipt['outcome'] == 'REJECTED' and reason in receipt['reason_codes'],
        f'{field} adversarial mutation is rejected',
        str(receipt),
    )

_tampered = copy.deepcopy(_BASE)
_tampered['source_snapshot']['telemetry']['sequence'] = 999
_tampered_receipt = validate_t3_candidate(_tampered, current_exact_head=_HEAD)
check(
    _tampered_receipt['outcome'] == 'REJECTED'
    and 'SOURCE_SNAPSHOT_TAMPERED' in _tampered_receipt['reason_codes'],
    'tampered source snapshot is rejected',
)

_result_tampered = copy.deepcopy(_BASE)
_result_tampered['result']['score_q16'] = 0
_result_tampered_receipt = validate_t3_candidate(
    _result_tampered,
    current_exact_head=_HEAD,
)
check(
    _result_tampered_receipt['outcome'] == 'REJECTED'
    and 'RESULT_DIGEST_MISMATCH' in _result_tampered_receipt['reason_codes'],
    'tampered result payload is rejected',
)

_wrong_head = validate_t3_candidate(_BASE, current_exact_head='b' * 40)
check(
    _wrong_head['outcome'] == 'REJECTED'
    and 'EXACT_HEAD_MISMATCH' in _wrong_head['reason_codes'],
    'candidate from a different exact head is rejected',
)

_unpinned = validate_t3_candidate(_BASE, current_exact_head='dev')
check(
    _unpinned['outcome'] == 'REJECTED'
    and 'RUNTIME_HEAD_UNPINNED' in _unpinned['reason_codes'],
    'unpinned runtime head fails closed',
)

_negative = copy.deepcopy(_BASE)
_negative['falsifier_status'] = 'NOT_SUPPORTED'
_negative_receipt = validate_t3_candidate(_negative, current_exact_head=_HEAD)
check(
    _negative_receipt['outcome'] == 'STRUCTURALLY_VALID',
    'negative scientific result remains valid evidence',
)

# Source-pin the bridge boundary itself. The T3 POST endpoint must never call
# any production mutation or routing primitive.
_bridge_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bridge.py')
with open(_bridge_path, encoding='utf-8') as handle:
    _bridge = handle.read()

_begin = '# ─── T3 CANDIDATE INTAKE BEGIN ───'
_end = '# ─── T3 CANDIDATE INTAKE END ───'
check(
    _bridge.count(_begin) == 1 and _bridge.count(_end) == 1,
    'bridge has exactly one source-pinned T3 candidate boundary',
)

if _begin in _bridge and _end in _bridge:
    _block = _bridge.split(_begin, 1)[1].split(_end, 1)[0]
    for forbidden in (
        'gate.record_signal(',
        'matrix.receive_gate_signal(',
        'matrix.process_event(',
        'router.route(',
        'save_checkpoint(',
    ):
        check(
            forbidden not in _block,
            f'T3 candidate boundary forbids {forbidden}',
        )

print(f'\n{PASS} passed, {FAIL} failed')
sys.exit(1 if FAIL else 0)
