"""
AEGIS M1 checkpoint v2 — startup envelope preflight.

The bridge calls checkpoint_exists() before entering its restore try/except.
Therefore corrupt v2 state must be rejected by the default-path existence
preflight, while a self-consistent checkpoint from another M1 geometry remains
an envelope-valid file for matrix-bound load_checkpoint() to reject later.
"""

import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import threading

LEDGER_PATH = pathlib.Path(__file__).resolve().parents[1] / 'ledger_persist.py'
PASS = 0
FAIL = 0


def _check(name: str, condition: bool, detail: str = '') -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  PASS  {name}')
    else:
        FAIL += 1
        suffix = f': {detail}' if detail else ''
        print(f'  FAIL  {name}{suffix}')


def _load_ledger():
    spec = importlib.util.spec_from_file_location('ledger_preflight_test', LEDGER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class Matrix:
    def __init__(self, region_bytes=400, sequence=1, epoch=2, era=3):
        self._m1_region = bytearray(region_bytes)
        self._sequence = sequence
        self._epoch = epoch
        self._era = era
        self._lock = threading.RLock()
        if sequence > 0:
            prev = sequence - 1
            capacity = region_bytes // 40
            offset = 40 * (prev % capacity)
            chain_hash = hashlib.sha256(f'chain:{prev}'.encode()).digest()
            self._m1_region[offset:offset + 40] = prev.to_bytes(8, 'little') + chain_hash


def _integrity(cp: dict) -> str:
    material = (
        f'{cp["checkpoint_version"]}:{cp["m1_record_contract"]}:'
        f'{cp["m1_region_bytes"]}:{cp["sequence"]}:{cp["epoch"]}:'
        f'{cp["era"]}:{cp["last_m1_entry_hex"]}'
    ).encode()
    return hashlib.sha256(material).hexdigest()


def _with_default(ledger, path: str, fn):
    old_default = ledger.DEFAULT_CHECKPOINT_PATH
    old_legacy = ledger.LEGACY_CHECKPOINT_PATH
    ledger.DEFAULT_CHECKPOINT_PATH = path
    ledger.LEGACY_CHECKPOINT_PATH = path + '.legacy'
    try:
        return fn()
    finally:
        ledger.DEFAULT_CHECKPOINT_PATH = old_default
        ledger.LEGACY_CHECKPOINT_PATH = old_legacy


def _expect_default_rejected(ledger, path: str) -> bool:
    def run():
        try:
            ledger.checkpoint_exists()
            return False
        except ledger.CheckpointError:
            return True
    return _with_default(ledger, path, run)


def _expect_default_exists(ledger, path: str) -> bool:
    def run():
        try:
            return ledger.checkpoint_exists() is True
        except ledger.CheckpointError:
            return False
    return _with_default(ledger, path, run)


def test_valid_v2_envelope_passes_preflight():
    ledger = _load_ledger()
    matrix = Matrix()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        ledger.save_checkpoint(matrix, path)
        _check('valid v2 default checkpoint passes preflight', _expect_default_exists(ledger, path))


def test_invalid_json_rejected_before_restore():
    ledger = _load_ledger()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        pathlib.Path(path).write_text('{not-json')
        _check('invalid JSON is rejected by checkpoint_exists', _expect_default_rejected(ledger, path))


def test_version_contract_and_integrity_rejected_before_restore():
    ledger = _load_ledger()
    matrix = Matrix()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        ledger.save_checkpoint(matrix, path)
        original = json.loads(pathlib.Path(path).read_text())

        wrong_version = dict(original)
        wrong_version['checkpoint_version'] = '9.9.9'
        wrong_version['integrity_hash'] = _integrity(wrong_version)
        pathlib.Path(path).write_text(json.dumps(wrong_version))
        _check('wrong version is rejected by checkpoint_exists', _expect_default_rejected(ledger, path))

        wrong_contract = dict(original)
        wrong_contract['m1_record_contract'] = 'M1_FIXED_CHAIN_V1'
        wrong_contract['integrity_hash'] = _integrity(wrong_contract)
        pathlib.Path(path).write_text(json.dumps(wrong_contract))
        _check('wrong contract is rejected by checkpoint_exists', _expect_default_rejected(ledger, path))

        bad_integrity = dict(original)
        bad_integrity['integrity_hash'] = '00' * 32
        pathlib.Path(path).write_text(json.dumps(bad_integrity))
        _check('bad integrity is rejected by checkpoint_exists', _expect_default_rejected(ledger, path))


def test_entry_shape_and_embedded_sequence_rejected_before_restore():
    ledger = _load_ledger()
    matrix = Matrix(sequence=5)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        ledger.save_checkpoint(matrix, path)
        original = json.loads(pathlib.Path(path).read_text())

        truncated = dict(original)
        truncated['last_m1_entry_hex'] = 'aa' * 20
        truncated['integrity_hash'] = _integrity(truncated)
        pathlib.Path(path).write_text(json.dumps(truncated))
        _check('truncated entry is rejected by checkpoint_exists', _expect_default_rejected(ledger, path))

        wrong_sequence = dict(original)
        entry = bytes.fromhex(original['last_m1_entry_hex'])
        wrong_entry = (123).to_bytes(8, 'little') + entry[8:]
        wrong_sequence['last_m1_entry_hex'] = wrong_entry.hex()
        wrong_sequence['integrity_hash'] = _integrity(wrong_sequence)
        pathlib.Path(path).write_text(json.dumps(wrong_sequence))
        _check('embedded sequence mismatch is rejected by checkpoint_exists', _expect_default_rejected(ledger, path))


def test_false_replay_flag_rejected_before_restore():
    ledger = _load_ledger()
    matrix = Matrix()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        ledger.save_checkpoint(matrix, path)
        cp = json.loads(pathlib.Path(path).read_text())
        cp['is_replay_reconstructable'] = False
        pathlib.Path(path).write_text(json.dumps(cp))
        _check('false replay flag is rejected by checkpoint_exists', _expect_default_rejected(ledger, path))


def test_valid_other_geometry_is_envelope_valid_but_load_rejects():
    ledger = _load_ledger()
    source = Matrix(region_bytes=800)
    target = Matrix(region_bytes=400, sequence=17, epoch=4, era=2)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        ledger.save_checkpoint(source, path)
        _check(
            'self-consistent other-geometry checkpoint passes envelope preflight',
            _expect_default_exists(ledger, path),
        )
        try:
            ledger.load_checkpoint(target, path)
            rejected = False
        except ledger.CheckpointError:
            rejected = True
        _check('matrix-bound load rejects geometry mismatch', rejected)
        _check('geometry rejection leaves target sequence untouched', target._sequence == 17)


if __name__ == '__main__':
    print('AEGIS M1 checkpoint startup preflight v2')
    test_valid_v2_envelope_passes_preflight()
    test_invalid_json_rejected_before_restore()
    test_version_contract_and_integrity_rejected_before_restore()
    test_entry_shape_and_embedded_sequence_rejected_before_restore()
    test_false_replay_flag_rejected_before_restore()
    test_valid_other_geometry_is_envelope_valid_but_load_rejects()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
