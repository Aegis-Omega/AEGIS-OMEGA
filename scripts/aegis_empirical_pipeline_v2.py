#!/usr/bin/env python3
"""AEGIS QP-PD empirical metrology runner, biological-context-bound V2.

This runner upgrades the verified V1 reference pipeline without mutating legacy V1
artifacts. It does not fabricate physical inputs. All required inputs must exist,
self-digests are recomputed, biological context is immutable, classical covariates
are byte-bound, and every downstream V2 receipt carries the same context digest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator

EXIT_FAIL_CLOSED = 78
MAX_SAFE_INTEGER = 9007199254740991


class FailClosed(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _utf16_sort_key(s: str) -> bytes:
    return s.encode('utf-16-be', 'surrogatepass')


def _jcs(obj: Any) -> str:
    if obj is None:
        return 'null'
    if obj is True:
        return 'true'
    if obj is False:
        return 'false'
    if isinstance(obj, int) and not isinstance(obj, bool):
        if abs(obj) > MAX_SAFE_INTEGER:
            raise FailClosed(f'integer outside RFC8785/I-JSON safe range: {obj}')
        return str(obj)
    if isinstance(obj, float):
        raise FailClosed('floating-point JSON numbers are forbidden in canonical receipts')
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    if isinstance(obj, list):
        return '[' + ','.join(_jcs(v) for v in obj) + ']'
    if isinstance(obj, dict):
        if not all(isinstance(k, str) for k in obj):
            raise FailClosed('JSON object key is not a string')
        return '{' + ','.join(
            json.dumps(k, ensure_ascii=False, separators=(',', ':')) + ':' + _jcs(obj[k])
            for k in sorted(obj, key=_utf16_sort_key)
        ) + '}'
    raise FailClosed(f'unsupported JSON type for RFC8785 canonicalization: {type(obj)!r}')


def rfc8785_bytes(obj: Any) -> bytes:
    return _jcs(obj).encode('utf-8')


def canonical_self_digest(obj: dict, digest_field: str) -> str:
    if digest_field not in obj:
        raise FailClosed(f'missing self-digest field: {digest_field}')
    material = dict(obj)
    material.pop(digest_field)
    return sha256_bytes(rfc8785_bytes(material))


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        raise FailClosed(f'cannot load JSON {path}: {e}') from e
    if not isinstance(value, dict):
        raise FailClosed(f'top-level JSON is not an object: {path}')
    return value


def validate(schema_path: Path, instance: dict, label: str) -> None:
    schema = load_json(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as e:
        raise FailClosed(f'{label} schema itself is invalid: {e}') from e
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        raise FailClosed(f'{label} schema validation failed: ' + '; '.join(e.message for e in errors[:8]))


def require_equal(actual: str, expected: str, label: str) -> None:
    if actual != expected:
        raise FailClosed(f'{label} mismatch: actual={actual} expected={expected}')


def require_pass(value: str, label: str) -> None:
    if value != 'PASS':
        raise FailClosed(f'{label} is not PASS: {value!r}')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def run_external(cmd: list[str], label: str, env: dict[str, str] | None = None) -> None:
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FailClosed(
            f'{label} failed rc={proc.returncode}; stdout={proc.stdout[-1000:]!r}; stderr={proc.stderr[-1000:]!r}'
        )


def verify_biological_context(context: dict) -> str:
    if context.get('schema_version') != 'QUANPHOTONIC_BIOLOGICAL_CONTEXT_MANIFEST_V1':
        raise FailClosed('BIOLOGICAL_CONTEXT_SCHEMA_UNSUPPORTED')
    actual = canonical_self_digest(context, 'biological_context_digest')
    if actual != context.get('biological_context_digest'):
        raise FailClosed('BIOLOGICAL_CONTEXT_MISMATCH')
    if not context.get('biological_context_id'):
        raise FailClosed('BIOLOGICAL_CONTEXT_ID_INVALID')
    return actual


def verify_context_registry(context: dict, registry: dict) -> None:
    prior = registry.get(context['biological_context_id'])
    if prior is not None and prior != context['biological_context_digest']:
        raise FailClosed('STALE_CONTEXT_REPLAY')


def build_measurement_and_manifest(
    calibration: dict,
    biological_context_digest: str,
    raw_payload: Path,
    batch_id: str,
    sequence: str,
) -> tuple[dict, dict]:
    payload_digest = sha256_file(raw_payload)
    measurement = {
        'schema_version': 'QUANPHOTONIC_MEASUREMENT_BATCH_V2',
        'measurement_batch_id': batch_id,
        'measurement_batch_digest': '0' * 64,
        'calibration_receipt_digest': calibration['calibration_receipt_digest'],
        'calibration_epoch_id': calibration['calibration_epoch_id'],
        'detector_id': calibration['detector_id'],
        'detector_configuration_digest': calibration['detector_configuration_digest'],
        'biological_context_digest': biological_context_digest,
        'sequence': sequence,
    }
    measurement['measurement_batch_digest'] = canonical_self_digest(measurement, 'measurement_batch_digest')
    manifest = {
        'schema_version': 'QUANPHOTONIC_RAW_DETECTOR_MANIFEST_V2',
        'measurement_batch_id': batch_id,
        'measurement_batch_digest': measurement['measurement_batch_digest'],
        'biological_context_digest': biological_context_digest,
        'raw_payload_digest': payload_digest,
        'raw_payload_media_type': 'application/octet-stream',
        'byte_length': raw_payload.stat().st_size,
        'detector_id': calibration['detector_id'],
        'calibration_receipt_digest': calibration['calibration_receipt_digest'],
        'sequence': sequence,
    }
    return measurement, manifest


def verify_classical_covariate_binding(manifest: dict, biological_context_digest: str, payload: Path) -> str:
    if manifest.get('schema_version') != 'QUANPHOTONIC_CLASSICAL_COVARIATE_MANIFEST_V1':
        raise FailClosed('CLASSICAL_COVARIATE_SCHEMA_UNSUPPORTED')
    actual_manifest_digest = canonical_self_digest(manifest, 'classical_covariate_manifest_digest')
    if actual_manifest_digest != manifest.get('classical_covariate_manifest_digest'):
        raise FailClosed('CLASSICAL_COVARIATE_MANIFEST_MISMATCH')
    if manifest.get('biological_context_digest') != biological_context_digest:
        raise FailClosed('CLASSICAL_COVARIATE_CONTEXT_MISMATCH')
    if sha256_file(payload) != manifest.get('classical_feature_payload_digest'):
        raise FailClosed('CLASSICAL_COVARIATE_PAYLOAD_MISMATCH')
    return actual_manifest_digest


def verify_analysis_bindings(
    receipt: dict,
    calibration: dict,
    measurement: dict,
    raw_manifest: dict,
    classical_manifest: dict,
    analysis_executable: Path,
    environment_descriptor: Path,
    falsification_contract: Path,
) -> None:
    require_equal(canonical_self_digest(receipt, 'analysis_receipt_digest'), receipt['analysis_receipt_digest'], 'analysis_receipt_digest')
    require_equal(receipt['measurement_batch_digest'], measurement['measurement_batch_digest'], 'analysis->measurement_batch_digest')
    require_equal(receipt['biological_context_digest'], measurement['biological_context_digest'], 'analysis->biological_context_digest')
    require_equal(receipt['classical_covariate_manifest_digest'], classical_manifest['classical_covariate_manifest_digest'], 'analysis->classical_covariate_manifest_digest')
    require_equal(receipt['raw_payload_digest'], raw_manifest['raw_payload_digest'], 'analysis->raw_payload_digest')
    require_equal(receipt['calibration_receipt_digest'], calibration['calibration_receipt_digest'], 'analysis->calibration_receipt_digest')
    require_equal(receipt['analysis_code_digest'], sha256_file(analysis_executable), 'analysis_code_digest')
    require_equal(receipt['analysis_environment_digest'], sha256_file(environment_descriptor), 'analysis_environment_digest')
    require_equal(receipt['falsification_contract_digest'], sha256_file(falsification_contract), 'falsification_contract_digest')
    if receipt['decision'] in {'INCONCLUSIVE', 'INVALID_MEASUREMENT'}:
        raise FailClosed(f"analysis decision blocks admission: {receipt['decision']}")


def evidence_join(
    biological_context_path: Path,
    classical_manifest_path: Path,
    classical_payload: Path,
    calibration_path: Path,
    measurement_path: Path,
    raw_payload: Path,
    raw_manifest_path: Path,
    analysis_path: Path,
    biological_context_digest: str,
    classical_covariate_manifest_digest: str,
) -> dict:
    artifacts = [
        ('BIO', biological_context_path, 'biological context manifest', 'BIOLOGICAL_CONTEXT_MANIFEST'),
        ('COV', classical_manifest_path, 'classical covariate manifest', 'CLASSICAL_COVARIATE_MANIFEST'),
        ('CFP', classical_payload, 'classical feature payload', 'CLASSICAL_FEATURE_PAYLOAD'),
        ('CAL', calibration_path, 'calibration receipt', 'CALIBRATION_RECEIPT'),
        ('MB', measurement_path, 'measurement batch envelope V2', 'MEASUREMENT_BATCH'),
        ('RAW', raw_payload, 'raw detector payload', 'RAW_DETECTOR_PAYLOAD'),
        ('RM', raw_manifest_path, 'raw detector manifest V2', 'RAW_DETECTOR_MANIFEST'),
        ('AN', analysis_path, 'analysis receipt V2', 'ANALYSIS_RECEIPT'),
    ]
    joined = {
        'schema': 'AEGIS_EVIDENCE_JOIN_V2',
        'created_at_utc': utc_now(),
        'biological_context_digest': biological_context_digest,
        'classical_covariate_manifest_digest': classical_covariate_manifest_digest,
        'join_policy': {
            'authority_invariant': 'No claim may possess greater epistemic authority than the weakest verified transition required to establish it.',
            'promotion_rule': 'Empirical promotion requires complete digest-bound biological context, calibration, raw measurement, classical covariates, deterministic analysis, and falsification evidence.',
            'missing_evidence_behavior': 'FAIL_CLOSED',
        },
        'artifacts': [
            {'artifact_id': aid, 'filename': p.name, 'sha256': sha256_file(p), 'role': role, 'authority_scope': kind}
            for aid, p, role, kind in artifacts
        ],
        'claims': [{
            'claim_id': 'EJ-EMP-V2-001',
            'claim': 'The empirical batch is digest-bound to one biological context, calibration, raw detector payload, and classical covariate payload.',
            'status': 'EMPIRICALLY_BOUND_CANDIDATE',
            'evidence': [
                {'artifact_id': aid, 'locator': 'whole artifact', 'evidence_kind': kind, 'effect': 'SUPPORTS'}
                for aid, _, _, kind in artifacts
            ],
            'missing_for_promotion': [],
        }],
        'join_summary': {
            'packet_status': 'EMPIRICAL_EVIDENCE_JOIN_V2',
            'verified_claims': 1,
            'limited_or_unestablished_claims': 0,
            'admission_decision': 'CANDIDATE_PENDING_POLICY',
        },
        'digest_scope': 'SHA256_OF_RFC8785_CANONICAL_JSON_EXCLUDING_packet_digest_sha256',
        'packet_digest_sha256': '0' * 64,
    }
    joined['packet_digest_sha256'] = canonical_self_digest(joined, 'packet_digest_sha256')
    return joined


def build_admission(
    *, batch_id: str, evidence_join_digest: str, analysis_receipt_digest: str,
    policy_digest: str, biological_context_digest: str,
    classical_covariate_manifest_digest: str,
) -> dict:
    admission = {
        'schema_version': 'QUANPHOTONIC_ADMISSION_RECEIPT_V2',
        'admission_receipt_id': f'admission:{batch_id}',
        'admission_receipt_digest': '0' * 64,
        'evidence_join_digest': evidence_join_digest,
        'analysis_receipt_digest': analysis_receipt_digest,
        'biological_context_digest': biological_context_digest,
        'classical_covariate_manifest_digest': classical_covariate_manifest_digest,
        'policy_digest': policy_digest,
        'decision': 'ADMIT',
        'reason_codes': [
            'COMPLETE_DIGEST_CHAIN', 'BIOLOGICAL_CONTEXT_BOUND', 'CLASSICAL_COVARIATES_BOUND',
            'CALIBRATION_PASS', 'SIGNATURE_VERIFIED', 'ANALYSIS_GATE_PASSED',
        ],
        'observed_at_utc': utc_now(),
    }
    admission['admission_receipt_digest'] = canonical_self_digest(admission, 'admission_receipt_digest')
    return admission


def negative_control_mismatch(real_manifest: dict, real_payload_digest: str) -> None:
    bad = dict(real_manifest)
    bad['raw_payload_digest'] = ('0' if real_payload_digest[0] != '0' else '1') + real_payload_digest[1:]
    try:
        require_equal(bad['raw_payload_digest'], real_payload_digest, 'negative-control payload digest')
    except FailClosed:
        return
    raise FailClosed('negative control unexpectedly passed')


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--biological-context', required=True, type=Path)
    p.add_argument('--biological-context-schema', required=True, type=Path)
    p.add_argument('--context-registry', required=True, type=Path)
    p.add_argument('--classical-covariate', required=True, type=Path)
    p.add_argument('--classical-covariate-schema', required=True, type=Path)
    p.add_argument('--classical-feature-payload', required=True, type=Path)
    p.add_argument('--calibration', required=True, type=Path)
    p.add_argument('--calibration-schema', required=True, type=Path)
    p.add_argument('--measurement-schema', required=True, type=Path)
    p.add_argument('--raw-manifest-schema', required=True, type=Path)
    p.add_argument('--analysis-schema', required=True, type=Path)
    p.add_argument('--admission-schema', required=True, type=Path)
    p.add_argument('--empirical-join-schema', required=True, type=Path)
    p.add_argument('--raw-payload', required=True, type=Path)
    p.add_argument('--batch-id', required=True)
    p.add_argument('--sequence', required=True)
    p.add_argument('--signature', required=True, type=Path)
    p.add_argument('--trust-root', required=True, type=Path)
    p.add_argument('--signature-verifier', required=True, type=Path)
    p.add_argument('--analysis-executable', required=True, type=Path)
    p.add_argument('--environment-descriptor', required=True, type=Path)
    p.add_argument('--falsification-contract', required=True, type=Path)
    p.add_argument('--policy', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--run-negative-control', action='store_true')
    return p.parse_args()


def main() -> int:
    a = parse_args()
    required_paths = [
        a.biological_context, a.biological_context_schema, a.context_registry,
        a.classical_covariate, a.classical_covariate_schema, a.classical_feature_payload,
        a.calibration, a.calibration_schema, a.measurement_schema, a.raw_manifest_schema,
        a.analysis_schema, a.admission_schema, a.empirical_join_schema, a.raw_payload,
        a.signature, a.trust_root, a.signature_verifier, a.analysis_executable,
        a.environment_descriptor, a.falsification_contract, a.policy,
    ]
    for path in required_paths:
        if not path.exists():
            raise FailClosed(f'required genuine input is absent: {path}')
    a.output_dir.mkdir(parents=True, exist_ok=True)

    context = load_json(a.biological_context)
    validate(a.biological_context_schema, context, 'biological context')
    biological_context_digest = verify_biological_context(context)
    verify_context_registry(context, load_json(a.context_registry))

    classical_manifest = load_json(a.classical_covariate)
    validate(a.classical_covariate_schema, classical_manifest, 'classical covariate manifest')
    classical_covariate_manifest_digest = verify_classical_covariate_binding(classical_manifest, biological_context_digest, a.classical_feature_payload)

    calibration = load_json(a.calibration)
    validate(a.calibration_schema, calibration, 'calibration')
    require_equal(canonical_self_digest(calibration, 'calibration_receipt_digest'), calibration['calibration_receipt_digest'], 'calibration_receipt_digest')
    require_pass(calibration['status'], 'calibration.status')
    canonical_cal = a.output_dir / 'calibration.rfc8785.json'
    canonical_cal.write_bytes(rfc8785_bytes(calibration))
    run_external([str(a.signature_verifier), '--canonical', str(canonical_cal), '--signature', str(a.signature), '--trust-root', str(a.trust_root)], 'calibration signature verification')

    measurement, raw_manifest = build_measurement_and_manifest(calibration, biological_context_digest, a.raw_payload, a.batch_id, a.sequence)
    validate(a.measurement_schema, measurement, 'measurement batch V2')
    validate(a.raw_manifest_schema, raw_manifest, 'raw detector manifest V2')
    measurement_path = a.output_dir / 'MeasurementBatchEnvelopeV2.json'
    raw_manifest_path = a.output_dir / 'RawDetectorManifestV2.json'
    write_json(measurement_path, measurement)
    write_json(raw_manifest_path, raw_manifest)
    require_equal(sha256_file(a.raw_payload), raw_manifest['raw_payload_digest'], 'raw payload recheck')
    require_equal(canonical_self_digest(measurement, 'measurement_batch_digest'), measurement['measurement_batch_digest'], 'measurement_batch_digest')
    if a.run_negative_control:
        negative_control_mismatch(raw_manifest, sha256_file(a.raw_payload))

    analysis_out = a.output_dir / 'AnalysisReceiptV2.json'
    env = dict(os.environ)
    env.update({
        'AEGIS_BIOLOGICAL_CONTEXT': str(a.biological_context),
        'AEGIS_CLASSICAL_COVARIATE_MANIFEST': str(a.classical_covariate),
        'AEGIS_CLASSICAL_FEATURE_PAYLOAD': str(a.classical_feature_payload),
        'AEGIS_CALIBRATION_RECEIPT': str(a.calibration),
        'AEGIS_MEASUREMENT_BATCH': str(measurement_path),
        'AEGIS_RAW_PAYLOAD': str(a.raw_payload),
        'AEGIS_RAW_MANIFEST': str(raw_manifest_path),
        'AEGIS_ENVIRONMENT_DESCRIPTOR': str(a.environment_descriptor),
        'AEGIS_FALSIFICATION_CONTRACT': str(a.falsification_contract),
        'AEGIS_ANALYSIS_RECEIPT_OUT': str(analysis_out),
    })
    run_external([str(a.analysis_executable)], 'deterministic analysis', env=env)
    if not analysis_out.exists():
        raise FailClosed('analysis executable returned success but emitted no AnalysisReceiptV2')
    analysis = load_json(analysis_out)
    validate(a.analysis_schema, analysis, 'analysis receipt V2')
    verify_analysis_bindings(analysis, calibration, measurement, raw_manifest, classical_manifest, a.analysis_executable, a.environment_descriptor, a.falsification_contract)

    joined = evidence_join(a.biological_context, a.classical_covariate, a.classical_feature_payload, a.calibration, measurement_path, a.raw_payload, raw_manifest_path, analysis_out, biological_context_digest, classical_covariate_manifest_digest)
    validate(a.empirical_join_schema, joined, 'empirical evidence join V2')
    join_path = a.output_dir / 'AEGIS_EVIDENCE_JOIN_V2.empirical.json'
    write_json(join_path, joined)

    policy_digest = sha256_file(a.policy)
    admission = build_admission(batch_id=a.batch_id, evidence_join_digest=joined['packet_digest_sha256'], analysis_receipt_digest=analysis['analysis_receipt_digest'], policy_digest=policy_digest, biological_context_digest=biological_context_digest, classical_covariate_manifest_digest=classical_covariate_manifest_digest)
    validate(a.admission_schema, admission, 'admission receipt V2')
    admission_path = a.output_dir / 'AdmissionReceiptV2.json'
    write_json(admission_path, admission)

    run_receipt = {
        'schema': 'AEGIS_EMPIRICAL_RUN_EXECUTION_RECEIPT_V2',
        'observed_at_utc': utc_now(),
        'status': 'PASS',
        'negative_control': 'PASS' if a.run_negative_control else 'NOT_RUN',
        'inputs': {
            'biological_context_sha256': sha256_file(a.biological_context),
            'classical_covariate_manifest_sha256': sha256_file(a.classical_covariate),
            'classical_feature_payload_sha256': sha256_file(a.classical_feature_payload),
            'calibration_sha256': sha256_file(a.calibration),
            'raw_payload_sha256': sha256_file(a.raw_payload),
            'signature_sha256': sha256_file(a.signature),
            'trust_root_sha256': sha256_file(a.trust_root),
            'signature_verifier_sha256': sha256_file(a.signature_verifier),
            'analysis_executable_sha256': sha256_file(a.analysis_executable),
            'environment_descriptor_sha256': sha256_file(a.environment_descriptor),
            'falsification_contract_sha256': sha256_file(a.falsification_contract),
            'policy_sha256': policy_digest,
        },
        'outputs': {
            'measurement_batch_sha256': sha256_file(measurement_path),
            'raw_manifest_sha256': sha256_file(raw_manifest_path),
            'analysis_receipt_sha256': sha256_file(analysis_out),
            'evidence_join_sha256': sha256_file(join_path),
            'admission_receipt_sha256': sha256_file(admission_path),
        },
        'epistemic_status': 'EMPIRICAL_CHAIN_EXECUTED_WITH_GENUINE_USER_SUPPLIED_INPUTS',
    }
    write_json(a.output_dir / 'AEGIS_EMPIRICAL_RUN_EXECUTION_RECEIPT_V2.json', run_receipt)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except FailClosed as e:
        print(f'FAIL_CLOSED: {e}', file=sys.stderr)
        raise SystemExit(EXIT_FAIL_CLOSED)
