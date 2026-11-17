"""OPTIMUS V17: source-bound M123 + V14 observer noninterference tests.

Run only on a staged candidate built from exact HOLON #813 and V14 #805
source blobs. These tests do not grant release or production authority.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core_matrix
from test_m123_contracts_v2 import matrix_fixture
from transition_observer import TransitionObserver
from transition_info import TransitionStats, adjacent_mi_q16, entropy_rate_q16
from epoch_failsafe import EpochState
from ledger_persist import save_checkpoint, load_checkpoint


class HolonV14Integration(unittest.TestCase):
    def make(self, observe=False, slots=5):
        m = matrix_fixture(slots)
        m._pgcs = SimpleNamespace(snapshot=lambda seq: SimpleNamespace(passes_criterion=True))
        if observe:
            m._transition_observer = TransitionObserver()
            m._transition_observer_errors = 0
        return m

    def test_legacy_fixture_and_public_telemetry(self):
        m = self.make()
        self.assertIsNone(m.transition_analytics_snapshot())
        self.assertEqual(m.process_event(b'a', b'\x01', b'')['status'], 'OK')
        self.assertNotIn('transition_observer_v14', m.emit_vcg_telemetry())

    def test_same_governance_bytes_and_verdicts(self):
        a, b = self.make(), self.make(True)
        outcomes = [b'', b'\x00', b'\x01', b'\x01', b'', b'\x00', b'\x01']
        for n, v in enumerate(outcomes):
            payload = ('e' + str(n)).encode()
            self.assertEqual(a.process_event(payload, v, b'ctx'), b.process_event(payload, v, b'ctx'))
            self.assertEqual(bytes(a._m1_region), bytes(b._m1_region))
            self.assertEqual(bytes(a._m2_region), bytes(b._m2_region))
            self.assertEqual(bytes(a._m3_region), bytes(b._m3_region))
        self.assertEqual(a.emit_vcg_telemetry(), b.emit_vcg_telemetry())
        s = b.transition_analytics_snapshot()
        stats = TransitionStats.from_iterable([TransitionObserver.symbol(v) for v in outcomes], 3)
        self.assertEqual(s['entropy_rate_q16'], entropy_rate_q16(stats))
        self.assertEqual(s['adjacent_mi_q16'], adjacent_mi_q16(stats))
        self.assertEqual(s['sample_count'], len(outcomes))

    def test_failed_observer_does_not_change_commit(self):
        a, b = self.make(), self.make(True)
        b._transition_observer.observe_verifier = Mock(side_effect=RuntimeError('observer failure'))
        self.assertEqual(a.process_event(b'x', b'\x01', b'y'), b.process_event(b'x', b'\x01', b'y'))
        self.assertEqual(b._total_processed, 1)
        self.assertEqual(bytes(a._m1_region), bytes(b._m1_region))
        self.assertEqual(b._transition_observer_errors, 1)

    def test_invalid_or_frozen_event_never_observed(self):
        b = self.make(True)
        with self.assertRaises(ValueError):
            b.process_event(b'x', b'\x03', b'')
        b._failsafe._state = EpochState.FROZEN
        self.assertEqual(b.process_event(b'y', b'\x01', b'')['status'], 'FROZEN')
        self.assertEqual(b.transition_analytics_snapshot()['sample_count'], 0)

    def test_checkpoint_23_does_not_persist_observer(self):
        b = self.make(True)
        for v in [b'', b'\x00', b'\x01']:
            b.process_event(b'x', v, b'')
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'cp.json')
            save_checkpoint(b, path)
            record = json.loads(Path(path).read_text())
            self.assertEqual(record['checkpoint_version'], '2.3.0')
            self.assertNotIn('transition_observer', str(record))
            recovered = self.make()
            load_checkpoint(recovered, path)
            self.assertEqual(recovered._sequence, b._sequence)
            self.assertIsNone(recovered.transition_analytics_snapshot())


    def test_constructor_default_off_and_exact_opt_in(self):
        # The CI sets a 64 KiB real arena. Never allocate the 4 GiB default.
        self.assertLessEqual(core_matrix.ARRAY_TOTAL_BYTES, 131072)
        for setting, enabled in [('0', False), ('true', False), ('1', True)]:
            fake_pgcs = SimpleNamespace(
                start=lambda: None, stop=lambda: None,
                snapshot=lambda seq: SimpleNamespace(passes_criterion=True))
            with patch.dict(os.environ, {'AEGIS_TRANSITION_OBSERVER': setting}):
                with patch.object(core_matrix, 'detect_hardware',
                                  return_value=SimpleNamespace(platform='test', is_target_hardware=False)):
                    with patch.object(core_matrix, 'PGCSController', return_value=fake_pgcs):
                        matrix = core_matrix.CoreMatrix()
            self.assertEqual(matrix._transition_observer is not None, enabled)
            self.assertNotIn('transition_observer_v14', matrix.emit_vcg_telemetry())

    def test_callback_failure_cannot_uncommit_observed_event(self):
        m = self.make(True, slots=2)
        m.process_event(b'a', b'', b'')
        m.process_event(b'b', b'', b'')
        m._event_cb = Mock(side_effect=RuntimeError('notification failure'))
        result = m.process_event(b'c', b'\x01', b'')
        self.assertEqual(result['status'], 'COMMITTED_CALLBACK_ERROR')
        self.assertEqual(result['sequence'], 3)
        self.assertEqual(m.transition_analytics_snapshot()['sample_count'], 3)


if __name__ == '__main__':
    unittest.main()
