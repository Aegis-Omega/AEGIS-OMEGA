import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

SCRIPT = Path('scripts/quanphotonic_v2_binding.py')
PIPELINE = Path('scripts/aegis_empirical_pipeline_v2.py')
PROFILE = Path('governance/AEGIS_CANONICAL_DIGEST_PROFILE_V2.json')
SCHEMA_DIR = Path('schemas')


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()


def self_digest(obj, field):
    body = dict(obj)
    body.pop(field, None)
    return sha256(canonical_json(body)).hexdigest()


def context(context_id='ctx-a', sample='sample-a', condition='baseline', timepoint='T0'):
    x = {
        'schema_version': 'QUANPHOTONIC_BIOLOGICAL_CONTEXT_MANIFEST_V1',
        'biological_context_id': context_id,
        'biological_context_digest': '0' * 64,
        'model_class': 'DOPAMINERGIC_NEURON_SYSTEM',
        'disease_context': 'Parkinson-relevant mitochondrial/redox stress',
        'sample_or_batch_id': sample,
        'condition_id': condition,
        'genotype_or_perturbation_class': 'CONTROL',
        'timepoint_label': timepoint,
        'operator_blinding_state': 'BLINDED',
        'metadata_provenance_digest': 'a' * 64,
    }
    x['biological_context_digest'] = self_digest(x, 'biological_context_digest')
    return x


def measurement(ctx_digest, schema='QUANPHOTONIC_MEASUREMENT_BATCH_V2'):
    x = {
        'schema_version': schema,
        'measurement_batch_id': 'batch-1',
        'measurement_batch_digest': '0' * 64,
        'calibration_receipt_digest': 'b' * 64,
        'calibration_epoch_id': 'epoch-1',
        'detector_id': 'detector-1',
        'detector_configuration_digest': 'c' * 64,
        'biological_context_digest': ctx_digest,
        'sequence': '1',
    }
    if schema == 'QUANPHOTONIC_MEASUREMENT_BATCH_V1':
        x.pop('biological_context_digest')
    x['measurement_batch_digest'] = self_digest(x, 'measurement_batch_digest')
    return x


class V2BindingTests(unittest.TestCase):
    def run_gate(self, ctx=None, meas=None, extra=None):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            args = [sys.executable, str(SCRIPT)]
            if ctx is not None:
                p = td / 'context.json'; p.write_text(json.dumps(ctx)); args += ['--biological-context', str(p)]
            if meas is not None:
                p = td / 'measurement.json'; p.write_text(json.dumps(meas)); args += ['--measurement', str(p)]
            if extra:
                args += extra
            return subprocess.run(args, text=True, capture_output=True)

    def load_pipeline(self):
        self.assertTrue(PIPELINE.is_file(), 'V2 empirical runner is not implemented')
        spec = importlib.util.spec_from_file_location('aegis_empirical_pipeline_v2', PIPELINE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_accepts_v2_exact_context_binding(self):
        ctx = context()
        r = self.run_gate(ctx, measurement(ctx['biological_context_digest']))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('QP_PD_V2_BINDING_OK', r.stdout)

    def test_missing_context_fails_closed(self):
        ctx = context()
        r = self.run_gate(None, measurement(ctx['biological_context_digest']))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('BIOLOGICAL_CONTEXT_MISSING', r.stderr)

    def test_context_self_digest_mismatch_fails_closed(self):
        ctx = context(); ctx['condition_id'] = 'stress'
        r = self.run_gate(ctx, measurement(ctx['biological_context_digest']))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('BIOLOGICAL_CONTEXT_MISMATCH', r.stderr)

    def test_v1_downgrade_is_forbidden(self):
        ctx = context()
        r = self.run_gate(ctx, measurement(ctx['biological_context_digest'], 'QUANPHOTONIC_MEASUREMENT_BATCH_V1'))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('V1_DOWNGRADE_FORBIDDEN', r.stderr)

    def test_cross_sample_splicing_is_rejected(self):
        ctx_a = context('ctx-a', 'sample-a')
        ctx_b = context('ctx-b', 'sample-b')
        r = self.run_gate(ctx_b, measurement(ctx_a['biological_context_digest']))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('BIOLOGICAL_CONTEXT_MISMATCH', r.stderr)

    def test_context_replay_registry_rejects_id_digest_drift(self):
        ctx_old = context('ctx-fixed', 'sample-a', 'baseline', 'T0')
        ctx_new = context('ctx-fixed', 'sample-a', 'stress', 'T1')
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / 'registry.json'
            reg.write_text(json.dumps({'ctx-fixed': ctx_old['biological_context_digest']}))
            r = self.run_gate(ctx_new, measurement(ctx_new['biological_context_digest']), ['--context-registry', str(reg)])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('STALE_CONTEXT_REPLAY', r.stderr)

    def test_digest_profile_v2_covers_context_measurement_and_covariates(self):
        profile = json.loads(PROFILE.read_text())
        fields = profile['self_digest_fields']
        self.assertEqual(fields['QUANPHOTONIC_BIOLOGICAL_CONTEXT_MANIFEST_V1'], 'biological_context_digest')
        self.assertEqual(fields['QUANPHOTONIC_MEASUREMENT_BATCH_V2'], 'measurement_batch_digest')
        self.assertEqual(fields['QUANPHOTONIC_CLASSICAL_COVARIATE_MANIFEST_V1'], 'classical_covariate_manifest_digest')

    def test_v2_receipt_family_propagates_biological_context_digest(self):
        paths = [
            'quanphotonic-measurement-batch.v2.schema.json',
            'quanphotonic-raw-detector-manifest.v2.schema.json',
            'quanphotonic-analysis-receipt.v2.schema.json',
            'quanphotonic-admission-receipt.v2.schema.json',
        ]
        for name in paths:
            schema = json.loads((SCHEMA_DIR / name).read_text())
            self.assertIn('biological_context_digest', schema['required'], name)
            self.assertEqual(schema['properties']['biological_context_digest']['pattern'], '^[0-9a-f]{64}$', name)

    def test_classical_covariate_manifest_binds_context_and_payload(self):
        schema = json.loads((SCHEMA_DIR / 'quanphotonic-classical-covariate-manifest.v1.schema.json').read_text())
        required = set(schema['required'])
        self.assertIn('classical_covariate_manifest_digest', required)
        self.assertIn('biological_context_digest', required)
        self.assertIn('classical_feature_payload_digest', required)

    def test_empirical_runner_v2_builds_context_bound_measurement_and_raw_manifest(self):
        m = self.load_pipeline()
        ctx = context()
        calibration = {
            'calibration_receipt_digest': 'b' * 64,
            'calibration_epoch_id': 'epoch-1',
            'detector_id': 'detector-1',
            'detector_configuration_digest': 'c' * 64,
        }
        with tempfile.TemporaryDirectory() as td:
            payload = Path(td) / 'raw.bin'; payload.write_bytes(b'unit-test-fixture-not-empirical')
            batch, raw = m.build_measurement_and_manifest(calibration, ctx['biological_context_digest'], payload, 'batch-1', '1')
        self.assertEqual(batch['schema_version'], 'QUANPHOTONIC_MEASUREMENT_BATCH_V2')
        self.assertEqual(raw['schema_version'], 'QUANPHOTONIC_RAW_DETECTOR_MANIFEST_V2')
        self.assertEqual(batch['biological_context_digest'], ctx['biological_context_digest'])
        self.assertEqual(raw['biological_context_digest'], ctx['biological_context_digest'])

    def test_empirical_runner_v2_rejects_classical_covariate_payload_splicing(self):
        m = self.load_pipeline()
        ctx = context()
        with tempfile.TemporaryDirectory() as td:
            payload = Path(td) / 'classical.json'; payload.write_bytes(b'{"x":1}')
            manifest = {
                'schema_version': 'QUANPHOTONIC_CLASSICAL_COVARIATE_MANIFEST_V1',
                'classical_covariate_manifest_id': 'cov-1',
                'classical_covariate_manifest_digest': '0' * 64,
                'biological_context_digest': ctx['biological_context_digest'],
                'classical_feature_payload_digest': 'd' * 64,
                'classical_feature_payload_media_type': 'application/json',
                'feature_schema_digest': 'e' * 64,
            }
            manifest['classical_covariate_manifest_digest'] = m.canonical_self_digest(manifest, 'classical_covariate_manifest_digest')
            with self.assertRaisesRegex(m.FailClosed, 'CLASSICAL_COVARIATE_PAYLOAD_MISMATCH'):
                m.verify_classical_covariate_binding(manifest, ctx['biological_context_digest'], payload)

    def test_empirical_runner_v2_admission_carries_context_and_covariate_binding(self):
        m = self.load_pipeline()
        admission = m.build_admission(
            batch_id='batch-1', evidence_join_digest='1' * 64,
            analysis_receipt_digest='2' * 64, policy_digest='3' * 64,
            biological_context_digest='4' * 64, classical_covariate_manifest_digest='5' * 64,
        )
        self.assertEqual(admission['schema_version'], 'QUANPHOTONIC_ADMISSION_RECEIPT_V2')
        self.assertEqual(admission['biological_context_digest'], '4' * 64)
        self.assertEqual(admission['classical_covariate_manifest_digest'], '5' * 64)
        self.assertEqual(admission['admission_receipt_digest'], m.canonical_self_digest(admission, 'admission_receipt_digest'))


if __name__ == '__main__':
    unittest.main()
