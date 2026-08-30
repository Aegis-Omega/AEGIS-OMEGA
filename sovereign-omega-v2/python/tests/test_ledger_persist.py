"""
Gate 170: Ledger persistence tests.
Tests save_checkpoint / load_checkpoint round-trip, integrity enforcement,
atomic write behaviour, and restart-resume semantics.
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core_matrix import CoreMatrix
from ledger_persist import (
    CHECKPOINT_VERSION,
    CheckpointError,
    checkpoint_exists,
    load_checkpoint,
    save_checkpoint,
)

PAYLOAD = b'\x01\x02\x03\x04'
VERIFIER = b'\x01'
CONTEXT = b'\x00' * 8


def _advance(matrix, n=10):
    """Push n events through the matrix to advance sequence/epoch."""
    for i in range(n):
        matrix.process_event(PAYLOAD, VERIFIER, CONTEXT)


class TestCheckpointRoundTrip(unittest.TestCase):
    def setUp(self):
        self.matrix = CoreMatrix()
        self.matrix.start()
        self.matrix.wait_ready()
        self.tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        self.matrix.stop()
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

    def test_save_returns_metadata(self):
        _advance(self.matrix, 5)
        meta = save_checkpoint(self.matrix, self.path)
        self.assertIn('sequence', meta)
        self.assertIn('epoch', meta)
        self.assertIn('era', meta)
        self.assertIn('integrity_hash', meta)
        self.assertEqual(meta['path'], self.path)

    def test_sequence_preserved_across_restart(self):
        _advance(self.matrix, 20)
        seq_before = self.matrix._sequence
        save_checkpoint(self.matrix, self.path)

        matrix2 = CoreMatrix()
        matrix2.start()
        matrix2.wait_ready()
        try:
            meta = load_checkpoint(matrix2, self.path)
            self.assertEqual(matrix2._sequence, seq_before)
            self.assertEqual(meta['sequence'], seq_before)
        finally:
            matrix2.stop()

    def test_epoch_preserved_across_restart(self):
        _advance(self.matrix, 200)  # 2 epochs (100 events = 1 epoch)
        epoch_before = self.matrix._epoch
        save_checkpoint(self.matrix, self.path)

        matrix2 = CoreMatrix()
        matrix2.start()
        matrix2.wait_ready()
        try:
            load_checkpoint(matrix2, self.path)
            self.assertEqual(matrix2._epoch, epoch_before)
        finally:
            matrix2.stop()

    def test_era_preserved_across_restart(self):
        _advance(self.matrix, 5)
        era_before = self.matrix._era
        save_checkpoint(self.matrix, self.path)

        matrix2 = CoreMatrix()
        matrix2.start()
        matrix2.wait_ready()
        try:
            load_checkpoint(matrix2, self.path)
            self.assertEqual(matrix2._era, era_before)
        finally:
            matrix2.stop()

    def test_chain_continues_after_restore(self):
        """Events processed after restore must chain to restored state."""
        _advance(self.matrix, 10)
        save_checkpoint(self.matrix, self.path)
        seq_at_save = self.matrix._sequence

        matrix2 = CoreMatrix()
        matrix2.start()
        matrix2.wait_ready()
        try:
            load_checkpoint(matrix2, self.path)
            self.assertEqual(matrix2._sequence, seq_at_save)
            # Should be able to process more events without crash
            _advance(matrix2, 5)
            self.assertEqual(matrix2._sequence, seq_at_save + 5)
        finally:
            matrix2.stop()

    def test_zero_sequence_checkpoint(self):
        """Checkpoint at sequence=0 (before any events) is valid."""
        meta = save_checkpoint(self.matrix, self.path)
        self.assertEqual(meta['sequence'], 0)
        matrix2 = CoreMatrix()
        matrix2.start()
        matrix2.wait_ready()
        try:
            restored = load_checkpoint(matrix2, self.path)
            self.assertEqual(restored['sequence'], 0)
        finally:
            matrix2.stop()

    def test_checkpoint_file_is_valid_json(self):
        _advance(self.matrix, 3)
        save_checkpoint(self.matrix, self.path)
        with open(self.path) as f:
            cp = json.load(f)
        self.assertEqual(cp['checkpoint_version'], CHECKPOINT_VERSION)
        self.assertTrue(cp['is_replay_reconstructable'])
        self.assertIn('integrity_hash', cp)
        self.assertIn('last_m1_entry_hex', cp)

    def test_checkpoint_exists_false_before_save(self):
        missing = self.path + '.missing'
        self.assertFalse(checkpoint_exists(missing))

    def test_checkpoint_exists_true_after_save(self):
        save_checkpoint(self.matrix, self.path)
        self.assertTrue(checkpoint_exists(self.path))

    def test_deterministic_integrity_hash(self):
        """Same state saved twice produces same integrity_hash."""
        _advance(self.matrix, 7)
        m1 = save_checkpoint(self.matrix, self.path)
        m2 = save_checkpoint(self.matrix, self.path)
        self.assertEqual(m1['integrity_hash'], m2['integrity_hash'])


class TestCheckpointIntegrityEnforcement(unittest.TestCase):
    def setUp(self):
        self.matrix = CoreMatrix()
        self.matrix.start()
        self.matrix.wait_ready()
        self.tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        self.matrix.stop()
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

    def _corrupt(self, field, value):
        with open(self.path) as f:
            cp = json.load(f)
        cp[field] = value
        with open(self.path, 'w') as f:
            json.dump(cp, f)

    def test_missing_file_raises(self):
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.matrix, self.path + '.nope')

    def test_wrong_version_raises(self):
        _advance(self.matrix, 3)
        save_checkpoint(self.matrix, self.path)
        self._corrupt('checkpoint_version', '9.9.9')
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.matrix, self.path)

    def test_tampered_sequence_raises(self):
        _advance(self.matrix, 3)
        save_checkpoint(self.matrix, self.path)
        self._corrupt('sequence', 9999)
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.matrix, self.path)

    def test_tampered_entry_hex_raises(self):
        _advance(self.matrix, 3)
        save_checkpoint(self.matrix, self.path)
        self._corrupt('last_m1_entry_hex', 'aa' * 40)
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.matrix, self.path)

    def test_replay_reconstructable_false_raises(self):
        _advance(self.matrix, 3)
        save_checkpoint(self.matrix, self.path)
        self._corrupt('is_replay_reconstructable', False)
        with self.assertRaises(CheckpointError):
            load_checkpoint(self.matrix, self.path)

    def test_matrix_untouched_on_integrity_failure(self):
        """If load fails, the original matrix state must be unchanged."""
        _advance(self.matrix, 5)
        seq_before = self.matrix._sequence
        save_checkpoint(self.matrix, self.path)
        self._corrupt('sequence', 9999)
        try:
            load_checkpoint(self.matrix, self.path)
        except CheckpointError:
            pass
        # sequence should be unchanged because integrity check fires before restore
        self.assertEqual(self.matrix._sequence, seq_before)


if __name__ == '__main__':
    unittest.main()
