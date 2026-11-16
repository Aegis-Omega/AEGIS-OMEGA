"""HOLON M1/M2/M3 V2 regression against the ACTUAL core_matrix.py import.

Run: python -m unittest discover -s python/tests -p 'test_m123_contracts_v2.py' -v
Small memoryviews and a CoreMatrix.__new__ fixture avoid 4 GiB allocation.
The tests prove local contracts, not immutable history or E4 statistical coverage.
"""
import hashlib
import json
import os
import random
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace

os.environ.setdefault('AEGIS_ARRAY_BYTES', '65536')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core_matrix import CoreMatrix, M1, M2, M3
from epoch_failsafe import EpochState
from gradient_anchor import GradientAnchorCalibrator, DEFAULT_ANCHOR_TOKENS, AnchorToken
from hardware_config import INT_SCALE
from ledger_persist import CheckpointError, load_checkpoint, save_checkpoint, _integrity_hash
from calibration_checkpoint import (
    CalibrationCheckpointError, snapshot_calibration,
    prepare_calibration_restore, install_calibration
)


def oracle(payloads):
    prior = bytes(32)
    result = []
    for n, payload in enumerate(payloads):
        # PR #806 canonical digest format: do not change without new chain version.
        prior = hashlib.sha256(prior + hashlib.sha256(payload).digest()).digest()
        result.append(prior)
    return result


def matrix_fixture(slots=3):
    m = CoreMatrix.__new__(CoreMatrix)
    m._lock = threading.RLock()
    m._sequence = m._era = m._epoch = 0
    m._m1_region = memoryview(bytearray(slots * 40))
    m._m2_region = memoryview(bytearray(128))
    m._m3_region = memoryview(bytearray(128))
    m._m1_era_capacity = slots
    m._total_processed = 0
    m._total_verified = 0
    m._total_vcg_error_fixed = 0
    m._m3_active_length = 0
    m._last_gate_signal_sequence = -1
    m._last_gate_signal_accepted = None
    m._event_cb = None
    m._failsafe = SimpleNamespace(state=EpochState.ACTIVE)
    m._calibrator = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
    return m


class M1Invariants(unittest.TestCase):
    def test_sha_chain_equals_independent_oracle_across_wrap(self):
        state = memoryview(bytearray(121))
        payloads = [bytes([i % 256]) * (i % 7) for i in range(27)]
        for i, payload in enumerate(payloads):
            sequence, digest = M1(state, payload, i)
            self.assertEqual(sequence, i + 1)
            self.assertEqual(digest, oracle(payloads)[i])
            offset = (i % 3) * 40
            self.assertEqual(state[offset:offset + 40].tobytes(),
                             i.to_bytes(8, 'little') + digest)
        self.assertEqual(state[120], 0)

    def test_prior_event_tamper_changes_terminal_digest(self):
        def terminal(first):
            state = memoryview(bytearray(160))
            digest = b''
            for i, payload in enumerate((first, b'same', b'same')):
                _, digest = M1(state, payload, i)
            return digest
        self.assertNotEqual(terminal(b'a'), terminal(b'b'))

    def test_missing_or_repeated_sequence_rejected_without_mutation(self):
        state = memoryview(bytearray(80))
        M1(state, b'a', 0)
        old = bytes(state)
        with self.assertRaises(ValueError):
            M1(state, b'c', 2)
        with self.assertRaises(ValueError):
            M1(state, b'a', 0)
        self.assertEqual(bytes(state), old)

    def test_alias_payload_snapshotted(self):
        region = bytearray(160)
        region[50:60] = bytes(range(10))
        expected = bytes(region[50:60])
        _, digest = M1(memoryview(region), memoryview(region)[50:60], 0)
        self.assertEqual(digest, oracle([expected])[0])

    def test_short_and_readonly_rejected(self):
        with self.assertRaises(ValueError):
            M1(memoryview(bytearray(39)), b'a', 0)
        with self.assertRaises(ValueError):
            M1(memoryview(bytes(40)), b'a', 0)


class M2Invariants(unittest.TestCase):
    def test_pointwise_error_and_fail_closed_lcb(self):
        for c in (0, INT_SCALE // 2, INT_SCALE):
            for verified in (b'\x00', b'\x01'):
                e, l = M2(memoryview(bytearray(80)), verified, c, 0)
                y = INT_SCALE if verified == b'\x01' else 0
                self.assertEqual((e, l), (abs(c - y), 0))

    def test_disjoint_eight_byte_slots(self):
        state = memoryview(bytearray(64))
        for n in range(8):
            M2(state, b'\x00', 100 + n, n)
        for n in range(8):
            self.assertEqual(int.from_bytes(state[n*8:n*8+4], 'little'), 100+n)
        M2(state, b'\x00', 222, 8)
        self.assertEqual(int.from_bytes(state[:4], 'little'), 222)

    def test_no_event_class_bools_and_no_short_region(self):
        for v in (b'', b'\x02', b'\x03', b'\x01\x01'):
            with self.assertRaises(ValueError):
                M2(memoryview(bytearray(64)), v, INT_SCALE)
        with self.assertRaises(ValueError):
            M2(memoryview(bytearray(7)), b'\x01', INT_SCALE)


class M3Invariants(unittest.TestCase):
    def test_identity_and_zero_scale(self):
        buf = memoryview(bytearray(16))
        self.assertEqual(M3(buf, b'\x00\x80\xff', INT_SCALE),
                         (b'\x00\x80\xff', 0))
        result, distortion = M3(buf, b'\xff\x01', 0)
        self.assertEqual(result, b'\x00\x00')
        self.assertGreater(distortion, 0)

    def test_random_exact_projection_distance(self):
        rng = random.Random(20261116)
        for _ in range(256):
            payload = bytes(rng.randrange(256) for i in range(rng.randrange(20)))
            w = rng.randrange(2 * INT_SCALE)
            result, dist = M3(memoryview(bytearray(32)), payload, w)
            expected = bytes(min(255, (b * w) >> 16) for b in payload)
            self.assertEqual(result, expected)
            reference = 0 if not payload else (
                sum(abs(a - b) for a, b in zip(payload, expected)) * INT_SCALE
            ) // (len(payload) * 255)
            self.assertEqual(dist, reference)

    def test_no_silent_truncation_or_negative_scale(self):
        buf = memoryview(bytearray(b'xx'))
        with self.assertRaises(ValueError):
            M3(buf, b'abc', INT_SCALE)
        with self.assertRaises(ValueError):
            M3(buf, b'x', -1)
        self.assertEqual(bytes(buf), b'xx')

    def test_aliased_context_reads_original_bytes(self):
        data = bytearray(range(16))
        initial = bytes(data[4:12])
        scaled, _ = M3(memoryview(data), memoryview(data)[4:12], INT_SCALE // 2)
        self.assertEqual(scaled, bytes(x // 2 for x in initial))


class CoreMatrixIntegration(unittest.TestCase):
    def test_no_ground_truth_does_not_create_calibration(self):
        m = matrix_fixture()
        r = m.process_event(b'a', b'', b'hello')
        self.assertFalse(r['gate_accepted'])
        self.assertFalse(r['verified_outcome_available'])
        self.assertEqual(m._total_verified, 0)
        self.assertEqual(m._m3_active_length, 5)
        self.assertEqual(r['divergence_fixed'], 0)

    def test_one_observation_never_authorizes_gate(self):
        m = matrix_fixture()
        r = m.process_event(b'a', b'\x01', b'')
        self.assertEqual(r['vcg_error_fixed'], 0)
        self.assertFalse(r['gate_lcb_valid'])
        self.assertFalse(r['gate_accepted'])
        self.assertEqual(m._total_verified, 1)

    def test_external_gate_signal_is_not_ground_truth(self):
        m = matrix_fixture()
        m.receive_gate_signal('proposal', True, 0)
        self.assertEqual(m._total_verified, 0)
        self.assertEqual(m._last_gate_signal_sequence, 0)

    def test_invalid_input_does_not_advance_sequence(self):
        m = matrix_fixture()
        with self.assertRaises(ValueError):
            m.process_event(b'a', b'\x03', b'')
        self.assertEqual(m._sequence, 0)


class CheckpointV2(unittest.TestCase):
    def test_restart_terminal_chain_parity(self):
        start = matrix_fixture(3)
        full = matrix_fixture(3)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp.json')
            for i in range(8):
                payload = str(i).encode()
                self.assertEqual(
                    start.process_event(payload, b'', b'')['state_hash'],
                    full.process_event(payload, b'', b'')['state_hash'])
            meta = save_checkpoint(start, path)
            self.assertFalse(meta['is_replay_reconstructable'])
            with open(path, encoding='utf-8') as f:
                cp = json.load(f)
            self.assertEqual(cp['checkpoint_version'], '2.2.0')
            self.assertTrue(cp['is_calibration_continuation_supported'])
            restored = matrix_fixture(3)
            load_checkpoint(restored, path)
            for i in range(8, 24):
                payload = str(i).encode()
                self.assertEqual(
                    restored.process_event(payload, b'', b'')['state_hash'],
                    full.process_event(payload, b'', b'')['state_hash'])

    def test_calibration_counters_restore_exactly(self):
        initial = matrix_fixture(3)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp.json')
            for v in (b'\x00', b'', b'\x01', b'\x00', b''):
                initial.process_event(b'x', v, b'')
            initial.receive_gate_signal('proposal', True, 42)
            save_checkpoint(initial, path)
            later = matrix_fixture(3)
            load_checkpoint(later, path)
            self.assertEqual(later._sequence, 5)
            self.assertEqual(later._total_processed, 5)
            self.assertEqual(later._total_verified, 3)
            self.assertEqual(later._total_vcg_error_fixed,
                             initial._total_vcg_error_fixed)
            self.assertEqual(later._last_gate_signal_sequence, 42)
            self.assertEqual(later._last_gate_signal_accepted, True)
            self.assertEqual(later._m3_active_length, 0)

    def test_v2_0_is_not_silently_treated_as_v2_1(self):
        first = matrix_fixture()
        first.process_event(b'a', b'\x01', b'')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp.json')
            save_checkpoint(first, path)
            with open(path, encoding='utf-8') as h:
                body = json.load(h)
            body['checkpoint_version'] = '2.0.0'
            # Simulate a full rewrite with a correctly recomputed unkeyed
            # checksum; version and contract validation must still deny.
            body['integrity_hash'] = hashlib.sha256(json.dumps(
                {k: v for k, v in body.items() if k != 'integrity_hash'},
                ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                allow_nan=False
            ).encode()).hexdigest()
            with open(path, 'w', encoding='utf-8') as h:
                json.dump(body, h)
            restored = matrix_fixture()
            with self.assertRaises(CheckpointError):
                load_checkpoint(restored, path)
            self.assertEqual(restored._sequence, 0)

    def test_cannot_restore_into_live_matrix(self):
        start = matrix_fixture()
        live = matrix_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp.json')
            start.process_event(b'x', b'\x01', b'')
            live.process_event(b'y', b'\x01', b'')
            save_checkpoint(start, path)
            with self.assertRaises(CheckpointError):
                load_checkpoint(live, path)
            self.assertEqual(live._sequence, 1)

    def test_v1_checkpoint_refused_without_mutation(self):
        m = matrix_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'old.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'checkpoint_version': '1.0.0'}, f)
            with self.assertRaises(CheckpointError):
                load_checkpoint(m, path)
        self.assertEqual(m._sequence, 0)



class CalibrationContinuationV22(unittest.TestCase):
    def test_rle_is_lossless_and_preserves_convergence(self):
        source = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        for epoch in range(1, 251):
            source.calibrate_epoch(epoch)
        self.assertEqual(source.convergence_epochs(), 250)
        record = snapshot_calibration(source)
        # Stable token measurements compress to one batch + repetition count.
        self.assertEqual(len(record['measurement_runs']), 1)
        self.assertEqual(record['measurement_runs'][0][1], 250)
        self.assertLess(len(json.dumps(record)), 2500)
        target = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        prepared = prepare_calibration_restore(target, record, 250)
        install_calibration(target, prepared)
        self.assertEqual(target._state.measurements, source._state.measurements)
        self.assertEqual(target._state.w_scales, source._state.w_scales)
        self.assertEqual(target._velocities, source._velocities)
        self.assertEqual(target.convergence_epochs(), 250)
        self.assertEqual(target.passes_criterion(250), source.passes_criterion(250))
        self.assertEqual(target.compute_drift_index(), source.compute_drift_index())
        for epoch in range(251, 261):
            self.assertEqual(target.calibrate_epoch(epoch),
                             source.calibrate_epoch(epoch))

    def test_checkpoint_restores_calibration_across_epoch_boundary(self):
        live, restarted = matrix_fixture(3), matrix_fixture(3)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp.json')
            for i in range(1, 251):
                live.process_event(str(i).encode(), b'', b'token')
            self.assertEqual(live._epoch, 2)
            self.assertEqual(live._calibrator._state.epoch, 2)
            save_checkpoint(live, path)
            with open(path, encoding='utf-8') as h:
                cp = json.load(h)
            self.assertEqual(cp['checkpoint_version'], '2.2.0')
            self.assertTrue(cp['is_calibration_continuation_supported'])
            self.assertEqual(cp['calibration_snapshot']['epoch'], 2)
            load_checkpoint(restarted, path)
            self.assertEqual(restarted._calibrator._state.measurements,
                             live._calibrator._state.measurements)
            for i in range(251, 401):
                payload = str(i).encode()
                a = live.process_event(payload, b'', b'token')
                b = restarted.process_event(payload, b'', b'token')
                self.assertEqual(a['state_hash'], b['state_hash'])
                self.assertEqual(a['drift_index'], b['drift_index'])
            self.assertEqual(restarted._epoch, 4)
            self.assertEqual(restarted._calibrator._state.measurements,
                             live._calibrator._state.measurements)

    def test_changed_calibration_data_denied_even_with_forged_checksum(self):
        source = matrix_fixture(3)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp.json')
            for i in range(100):
                source.process_event(b'x', b'', b'')
            save_checkpoint(source, path)
            with open(path, encoding='utf-8') as h:
                cp = json.load(h)
            cp['calibration_snapshot']['measurement_runs'][0][2][0][1] += 1
            cp['integrity_hash'] = _integrity_hash({
                k: v for k, v in cp.items() if k != 'integrity_hash'
            })
            with open(path, 'w', encoding='utf-8') as h:
                json.dump(cp, h)
            target = matrix_fixture(3)
            with self.assertRaisesRegex(CheckpointError, 'calibration'):
                load_checkpoint(target, path)
            self.assertEqual(target._sequence, 0)
            self.assertEqual(target._calibrator._state.measurements, [])

    def test_mismatched_anchor_registry_denied_without_mutation(self):
        source = matrix_fixture(3)
        source.process_event(b'x', b'', b'')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp.json')
            save_checkpoint(source, path)
            target = matrix_fixture(3)
            target._calibrator.inject_anchor_token(AnchorToken(
                token_id='NEW_ANCHOR', token_hash='00' * 32,
                expected_w_scale=INT_SCALE, tolerance_fixed=0,
                description='Different trusted source'))
            with self.assertRaises(CheckpointError):
                load_checkpoint(target, path)
            self.assertEqual(target._sequence, 0)

    def test_calibrator_without_snapshot_is_refused_for_real_matrix(self):
        chain_only = SimpleNamespace(
            _lock=threading.RLock(),
            _m1_region=memoryview(bytearray(120)),
            _sequence=0, _epoch=0, _era=0,
            _total_processed=0, _total_verified=0,
            _total_vcg_error_fixed=0,
            _last_gate_signal_sequence=-1,
            _last_gate_signal_accepted=None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp.json')
            meta = save_checkpoint(chain_only, path)
            self.assertFalse(meta['is_calibration_continuation_supported'])
            target = matrix_fixture(3)
            with self.assertRaises(CheckpointError):
                load_checkpoint(target, path)
            self.assertEqual(target._sequence, 0)

    def test_resource_cap_rejects_overlarge_expansion(self):
        from unittest.mock import patch
        import calibration_checkpoint as codec
        source = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        source.calibrate_epoch(1)
        body = snapshot_calibration(source)
        target = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        with patch.object(codec, 'MAX_RESTORE_MEASUREMENTS', 4):
            with self.assertRaisesRegex(CalibrationCheckpointError, 'limit'):
                prepare_calibration_restore(target, body, 1)
            self.assertEqual(target._state.epoch, 0)
            self.assertEqual(target._state.measurements, [])

    def test_tampered_rle_run_denied_before_expansion(self):
        source = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        source.calibrate_epoch(1)
        body = snapshot_calibration(source)
        body['measurement_runs'][0][1] = 1000000000
        target = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        with self.assertRaises(CalibrationCheckpointError):
            prepare_calibration_restore(target, body, 1)
        self.assertEqual(target._state.measurements, [])

    def test_state_epoch_type_invalid_fails_closed(self):
        source = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        source._state.epoch = 'not-an-epoch'
        with self.assertRaises(CalibrationCheckpointError):
            snapshot_calibration(source)

    def test_nonreproducible_nonzero_anchor_initial_state_denied(self):
        source = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        source._state.w_scales['GATE_ACCEPT_THRESHOLD'] = INT_SCALE + 1
        with self.assertRaises(CalibrationCheckpointError):
            snapshot_calibration(source)


if __name__ == '__main__':
    unittest.main()
