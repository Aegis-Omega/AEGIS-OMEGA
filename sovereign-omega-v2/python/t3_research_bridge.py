"""AEGIS Ω — T0↔T3 research boundary helpers.

EPISTEMIC TIER: T0/T3 BOUNDARY

This module deliberately has no mutation-gate, execution-router, or CoreMatrix
dependency. It exposes a bounded T0/T1/T2 telemetry view to T3 research and
validates T3 experiment candidates structurally. A structurally valid candidate
is still advisory evidence only: it never grants promotion or write-back.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import canonical_envelope as _canon_env

SNAPSHOT_SCHEMA_VERSION = '1.0.0'
CANDIDATE_SCHEMA_VERSION = '1.0.0'
SNAPSHOT_KIND = 'AEGIS_T3_RESEARCH_SNAPSHOT_V1'
CANDIDATE_RECEIPT_KIND = 'AEGIS_T3_EXPERIMENT_CANDIDATE_RECEIPT_V1'
T3_RESEARCH_ONLY = True
WRITE_BACK_AUTHORITY = False
AUTHORITY_EFFECT = 'NONE'

_ALLOWED_MECHANISMS = frozenset({'DSR', 'RAR'})
_ALLOWED_FALSIFIER_STATUS = frozenset({
    'SUPPORTED', 'NOT_SUPPORTED', 'INCONCLUSIVE',
})
_ALLOWED_TARGETS = frozenset({'T2'})
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_COMMIT_SHA_RE = re.compile(r'^[0-9a-f]{40}(?:[0-9a-f]{24})?$')

# Explicit allow-list: adding a telemetry field to the T3 surface is a deliberate
# code change, never an accidental dump of the production runtime.
_TELEMETRY_FIELDS = (
    'sequence', 'epoch', 'avg_vcg_error', 'drift_index', 'corruption_count',
    'failsafe_state', 'pgcs_passes',
)
_GATE_FIELDS = (
    'gate_acceptance_rate', 'gate_window_size', 'gate_last_sequence',
    'gate_total_signals', 'gate_sealed',
)
_ROUTER_FIELDS = (
    'router_total_events', 'router_rejected', 'router_sealed',
)


def _bounded_text(value: Any, field: str, *, max_len: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > max_len:
        raise ValueError(
            f'{field} must be a non-empty string of at most {max_len} characters'
        )
    return value


def _sha256(value: Any, field: str) -> str:
    text = _bounded_text(value, field, max_len=64)
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f'{field} must be lowercase SHA-256 hex')
    return text


def _select(source: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: source[field] for field in fields if field in source}


def build_t3_research_snapshot(
    *,
    telemetry: Mapping[str, Any],
    gate_telemetry: Mapping[str, Any],
    router_telemetry: Mapping[str, Any],
    exact_head: str,
) -> dict[str, Any]:
    """Return a deterministic, read-only snapshot for T3 experimentation."""
    if not isinstance(telemetry, Mapping):
        raise TypeError('telemetry must be a mapping')
    if not isinstance(gate_telemetry, Mapping):
        raise TypeError('gate_telemetry must be a mapping')
    if not isinstance(router_telemetry, Mapping):
        raise TypeError('router_telemetry must be a mapping')
    exact_head = _bounded_text(exact_head, 'exact_head', max_len=128)

    body = {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'receipt_kind': SNAPSHOT_KIND,
        'exact_head': exact_head,
        'source_tier': 'T0_T2_TELEMETRY',
        'consumer_tier': 'T3',
        't3_research_only': T3_RESEARCH_ONLY,
        'write_back_authority': WRITE_BACK_AUTHORITY,
        'authority_effect': AUTHORITY_EFFECT,
        'telemetry': _select(telemetry, _TELEMETRY_FIELDS),
        'gate': _select(gate_telemetry, _GATE_FIELDS),
        'router': _select(router_telemetry, _ROUTER_FIELDS),
    }
    digest = _canon_env.payload_digest(body)
    return {**body, 'snapshot_digest': digest}


def validate_t3_candidate(
    candidate: Mapping[str, Any],
    *,
    current_exact_head: str,
) -> dict[str, Any]:
    """Validate a T3 experiment candidate without granting tier promotion.

    Structurally valid evidence may be consumed by the repository's existing
    experiment-admission process. This function cannot mutate production state,
    cannot grant T2/T1/T0 authority, and cannot request write-back.
    """
    reasons: list[str] = []
    current_exact_head = _bounded_text(
        current_exact_head, 'current_exact_head', max_len=128
    )
    if not _COMMIT_SHA_RE.fullmatch(current_exact_head):
        reasons.append('RUNTIME_HEAD_UNPINNED')

    if not isinstance(candidate, Mapping):
        candidate = {}
        reasons.append('CANDIDATE_NOT_MAPPING')

    if candidate.get('schema_version') != CANDIDATE_SCHEMA_VERSION:
        reasons.append('SCHEMA_VERSION_MISMATCH')

    mechanism_id = candidate.get('mechanism_id')
    if mechanism_id not in _ALLOWED_MECHANISMS:
        reasons.append('UNKNOWN_MECHANISM')

    experiment_id = candidate.get('experiment_id')
    try:
        _bounded_text(experiment_id, 'experiment_id', max_len=128)
    except ValueError:
        reasons.append('INVALID_EXPERIMENT_ID')

    source_snapshot = candidate.get('source_snapshot')
    source_snapshot_digest = candidate.get('source_snapshot_digest')
    if not isinstance(source_snapshot, Mapping):
        reasons.append('SOURCE_SNAPSHOT_MISSING')
    else:
        supplied_snapshot_digest = source_snapshot.get('snapshot_digest')
        snapshot_body = dict(source_snapshot)
        snapshot_body.pop('snapshot_digest', None)
        recomputed = _canon_env.payload_digest(snapshot_body)

        if supplied_snapshot_digest != recomputed:
            reasons.append('SOURCE_SNAPSHOT_TAMPERED')
        if source_snapshot_digest != recomputed:
            reasons.append('SOURCE_SNAPSHOT_DIGEST_MISMATCH')
        if source_snapshot.get('receipt_kind') != SNAPSHOT_KIND:
            reasons.append('SOURCE_SNAPSHOT_KIND_INVALID')
        if source_snapshot.get('t3_research_only') is not True:
            reasons.append('SOURCE_NOT_T3_RESEARCH_ONLY')
        if source_snapshot.get('write_back_authority') is not False:
            reasons.append('SOURCE_WRITE_BACK_NOT_FALSE')
        if source_snapshot.get('authority_effect') != AUTHORITY_EFFECT:
            reasons.append('SOURCE_AUTHORITY_EFFECT_NOT_NONE')
        if source_snapshot.get('exact_head') != current_exact_head:
            reasons.append('EXACT_HEAD_MISMATCH')

    for field in ('config_digest', 'result_digest'):
        try:
            _sha256(candidate.get(field), field)
        except ValueError:
            reasons.append(f'INVALID_{field.upper()}')

    if candidate.get('falsifier_status') not in _ALLOWED_FALSIFIER_STATUS:
        reasons.append('INVALID_FALSIFIER_STATUS')

    if candidate.get('requested_target_tier') not in _ALLOWED_TARGETS:
        reasons.append('DIRECT_OR_INVALID_TIER_PROMOTION')

    if candidate.get('authority_effect') != AUTHORITY_EFFECT:
        reasons.append('AUTHORITY_EFFECT_MUST_BE_NONE')

    if candidate.get('write_back_requested') is not False:
        reasons.append('WRITE_BACK_FORBIDDEN')

    reasons = sorted(set(reasons))
    structurally_valid = not reasons

    body = {
        'schema_version': CANDIDATE_SCHEMA_VERSION,
        'receipt_kind': CANDIDATE_RECEIPT_KIND,
        'current_exact_head': current_exact_head,
        'experiment_id': (
            experiment_id if isinstance(experiment_id, str) else None
        ),
        'mechanism_id': (
            mechanism_id if isinstance(mechanism_id, str) else None
        ),
        'source_snapshot_digest': (
            source_snapshot_digest
            if isinstance(source_snapshot_digest, str)
            else None
        ),
        'config_digest': (
            candidate.get('config_digest')
            if isinstance(candidate.get('config_digest'), str)
            else None
        ),
        'result_digest': (
            candidate.get('result_digest')
            if isinstance(candidate.get('result_digest'), str)
            else None
        ),
        'falsifier_status': (
            candidate.get('falsifier_status')
            if isinstance(candidate.get('falsifier_status'), str)
            else None
        ),
        'requested_target_tier': (
            candidate.get('requested_target_tier')
            if isinstance(candidate.get('requested_target_tier'), str)
            else None
        ),
        'outcome': (
            'STRUCTURALLY_VALID' if structurally_valid else 'REJECTED'
        ),
        'promotion_granted': False,
        'next_required_gate': (
            'AEGIS_EXPERIMENT_ADMISSION'
            if structurally_valid
            else None
        ),
        't3_research_only': T3_RESEARCH_ONLY,
        'write_back_authority': WRITE_BACK_AUTHORITY,
        'authority_effect': AUTHORITY_EFFECT,
        'reason_codes': reasons,
    }
    return {**body, 'receipt_hash': _canon_env.payload_digest(body)}
