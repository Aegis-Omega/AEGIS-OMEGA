"""M1 cross-event integrity and V2 checkpoint regression tests."""
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from m1_chain import M1
from ledger_persist import (CHECKPOINT_VERSION, CHAIN_MODE, CheckpointError,
                            save_checkpoint, load_checkpoint)


class FakeMatrix:
    def __init__(self, size=163):
        self._m1_region = memoryview(bytearray(size))
        self._lock = threading.RLock()
        self._sequence = self._epoch = self._era = 0

    def add(self, payload):
        self._sequence, digest = M1(self._m1_region, payload, self._sequence)
        return digest


class TestM1V2(unittest.TestCase):
    def test_chain_transitivity(self):
        m = FakeMatrix(257)
        previous = b'\x00' * 32
        for i, payload in enumerate((b'alpha', b'beta', b'gamma')):
            previous = hashlib.sha256(previous + hashlib.sha256(payload).digest()).digest()
            self.assertEqual(m.add(payload), previous)
            self.assertEqual(bytes(m._m1_region[i * 40:i * 40 + 8]),
                             i.to_bytes(8, 'little'))
        n = FakeMatrix(257)
        for payload in (b'changed', b'beta', b'gamma'):
            last = n.add(payload)
        self.assertNotEqual(last, previous)

    def test_complete_slots_and_wrap(self):
        m = FakeMatrix(167)   # 4 slots and 7 padding bytes
        previous = b'\x00' * 32
        for i in range(29):
            payload = f'e{i}'.encode()
            previous = hashlib.sha256(previous + hashlib.sha256(payload).digest()).digest()
            self.assertEqual(m.add(payload), previous)
        self.assertEqual(bytes(m._m1_region[-7:]), b'\x00' * 7)

    def test_missing_predecessor_fails_without_mutation(self):
        region = memoryview(bytearray(160))
        with self.assertRaises(ValueError):
            M1(region, b'x', 1)
        self.assertEqual(bytes(region), b'\x00' * 160)

    def test_short_state_and_invalid_sequence(self):
        for length, sequence in ((39, 0), (80, -1), (80, (1 << 64) - 1)):
            with self.assertRaises(ValueError):
                M1(memoryview(bytearray(length)), b'x', sequence)


class TestCheckpointV2(unittest.TestCase):
    def checkpoint(self, m):
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        save_checkpoint(m, path)
        return path

    def test_resume_equals_uninterrupted(self):
        m = FakeMatrix()
        for i in range(12):
            m.add(str(i).encode())
        cp = self.checkpoint(m)
        with open(cp, encoding='utf-8') as h:
            data = json.load(h)
        self.assertEqual(data['checkpoint_version'], CHECKPOINT_VERSION)
        self.assertEqual(data['chain_mode'], CHAIN_MODE)
        self.assertFalse(data['is_replay_reconstructable'])
        self.assertTrue(data['is_chain_continuation_supported'])
        restored = FakeMatrix()
        load_checkpoint(restored, cp)
        self.assertEqual(restored.add(b'next'), m.add(b'next'))

    def test_legacy_v1_rejected(self):
        m = FakeMatrix()
        m.add(b'first')
        cp = self.checkpoint(m)
        with open(cp, encoding='utf-8') as h:
            data = json.load(h)
        data['checkpoint_version'] = '1.0.0'
        with open(cp, 'w', encoding='utf-8') as h:
            json.dump(data, h)
        candidate = FakeMatrix()
        with self.assertRaises(CheckpointError):
            load_checkpoint(candidate, cp)
        self.assertEqual(candidate._sequence, 0)

    def test_wrong_capacity_rejected(self):
        m = FakeMatrix(201)
        m.add(b'first')
        cp = self.checkpoint(m)
        candidate = FakeMatrix(160)
        with self.assertRaisesRegex(CheckpointError, 'capacity'):
            load_checkpoint(candidate, cp)
        self.assertEqual(candidate._sequence, 0)

    def test_tampered_header_rejected_even_with_updated_checksum(self):
        m = FakeMatrix()
        m.add(b'first')
        cp = self.checkpoint(m)
        with open(cp, encoding='utf-8') as h:
            data = json.load(h)
        data['sequence'] = 3
        data['integrity_hash'] = hashlib.sha256(json.dumps(
            {k:v for k,v in data.items() if k != 'integrity_hash'},
            sort_keys=True, ensure_ascii=False, separators=(',', ':'),
            allow_nan=False,
        ).encode()).hexdigest()
        with open(cp, 'w', encoding='utf-8') as h:
            json.dump(data, h)
        candidate = FakeMatrix()
        with self.assertRaises(CheckpointError):
            load_checkpoint(candidate, cp)
        self.assertEqual(candidate._sequence, 0)


if __name__ == '__main__':
    unittest.main()
