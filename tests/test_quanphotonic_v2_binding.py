import json
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

SCRIPT = Path('scripts/quanphotonic_v2_binding.py')


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


if __name__ == '__main__':
    unittest.main()
