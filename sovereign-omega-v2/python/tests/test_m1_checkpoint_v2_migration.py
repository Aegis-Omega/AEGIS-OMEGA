"""
AEGIS M1 checkpoint v2 migration and startup fail-closed regression.
"""

import ast
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import threading

PYTHON_DIR = pathlib.Path(__file__).resolve().parents[1]
LEDGER_PATH = PYTHON_DIR / 'ledger_persist.py'
BRIDGE_PATH = PYTHON_DIR / 'bridge.py'

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
    spec = importlib.util.spec_from_file_location('ledger_persist_migration_test', LEDGER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class Matrix:
    def __init__(self, region_bytes=400, sequence=0, epoch=0, era=0):
        self._m1_region = bytearray(region_bytes)
        self._sequence = sequence
        self._epoch = epoch
        self._era = era
        self._lock = threading.RLock()


def _tmp_path():
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    return path


def test_checkpoint_v2_schema_and_geometry_binding():
    ledger = _load_ledger()
    _check('checkpoint version is 2.0.0', ledger.CHECKPOINT_VERSION == '2.0.0')
    _check(
        'checkpoint declares fixed-chain v2 contract',
        getattr(ledger, 'M1_RECORD_CONTRACT', None) == 'M1_FIXED_CHAIN_V2',
    )

    matrix = Matrix(region_bytes=400, sequence=1, epoch=2, era=3)
    matrix._m1_region[0:40] = (0).to_bytes(8, 'little') + b'\x22' * 32
    path = _tmp_path()
    try:
        ledger.save_checkpoint(matrix, path)
        cp = json.loads(pathlib.Path(path).read_text())
        _check('checkpoint stores v2 version', cp.get('checkpoint_version') == '2.0.0')
        _check('checkpoint stores M1 contract id', cp.get('m1_record_contract') == 'M1_FIXED_CHAIN_V2')
        _check('checkpoint stores active M1 region bytes', cp.get('m1_region_bytes') == 400)

        cp_contract = dict(cp)
        cp_contract['m1_record_contract'] = 'M1_FIXED_CHAIN_V1'
        pathlib.Path(path).write_text(json.dumps(cp_contract))
        target = Matrix(region_bytes=400, sequence=9, epoch=9, era=9)
        try:
            ledger.load_checkpoint(target, path)
            contract_rejected = False
        except ledger.CheckpointError:
            contract_rejected = True
        _check('tampered contract id is rejected', contract_rejected)
        _check('contract rejection leaves matrix untouched', target._sequence == 9)

        pathlib.Path(path).write_text(json.dumps(cp))
        wrong_geometry = Matrix(region_bytes=800, sequence=7, epoch=7, era=7)
        try:
            ledger.load_checkpoint(wrong_geometry, path)
            geometry_rejected = False
        except ledger.CheckpointError:
            geometry_rejected = True
        _check('checkpoint geometry mismatch is rejected', geometry_rejected)
        _check('geometry rejection leaves matrix untouched', wrong_geometry._sequence == 7)
    finally:
        pathlib.Path(path).unlink(missing_ok=True)


def test_legacy_v1_checkpoint_is_rejected():
    ledger = _load_ledger()
    entry_hex = ('00' * 8) + ('11' * 32)
    sequence = 1
    epoch = 0
    era = 0
    legacy_integrity = hashlib.sha256(
        f'{sequence}:{epoch}:{era}:{entry_hex}'.encode()
    ).hexdigest()
    legacy = {
        'checkpoint_version': '1.0.0',
        'sequence': sequence,
        'epoch': epoch,
        'era': era,
        'last_m1_entry_hex': entry_hex,
        'integrity_hash': legacy_integrity,
        'is_replay_reconstructable': True,
    }
    path = _tmp_path()
    pathlib.Path(path).write_text(json.dumps(legacy))
    target = Matrix(region_bytes=400, sequence=17, epoch=4, era=2)
    try:
        try:
            ledger.load_checkpoint(target, path)
            rejected = False
        except ledger.CheckpointError:
            rejected = True
        _check('legacy v1 checkpoint is rejected', rejected)
        _check('legacy rejection leaves sequence untouched', target._sequence == 17)
        _check('legacy rejection leaves epoch untouched', target._epoch == 4)
        _check('legacy rejection leaves era untouched', target._era == 2)
    finally:
        pathlib.Path(path).unlink(missing_ok=True)


def test_versioned_default_namespace_detects_legacy_checkpoint():
    ledger = _load_ledger()
    _check(
        'default checkpoint filename is v2 namespaced',
        pathlib.Path(ledger.DEFAULT_CHECKPOINT_PATH).name == 'aegis_checkpoint_v2.json',
    )
    _check(
        'legacy checkpoint filename is explicit',
        pathlib.Path(getattr(ledger, 'LEGACY_CHECKPOINT_PATH', '')).name == 'aegis_checkpoint.json',
    )

    original_default = ledger.DEFAULT_CHECKPOINT_PATH
    original_legacy = getattr(ledger, 'LEGACY_CHECKPOINT_PATH', '')
    with tempfile.TemporaryDirectory() as tmpdir:
        v2_path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        v1_path = os.path.join(tmpdir, 'aegis_checkpoint.json')
        ledger.DEFAULT_CHECKPOINT_PATH = v2_path
        ledger.LEGACY_CHECKPOINT_PATH = v1_path
        pathlib.Path(v1_path).write_text('{}')
        try:
            try:
                ledger.checkpoint_exists()
                legacy_detected = False
            except ledger.CheckpointError:
                legacy_detected = True
            _check('legacy-only default state fails closed', legacy_detected)

            matrix = Matrix(region_bytes=400, sequence=1, epoch=0, era=0)
            matrix._m1_region[0:40] = (0).to_bytes(8, 'little') + b'\x33' * 32
            ledger.save_checkpoint(matrix, v2_path)
            try:
                v2_exists = ledger.checkpoint_exists()
            except ledger.CheckpointError:
                v2_exists = False
            _check('valid v2 checkpoint takes precedence when present', v2_exists)
        finally:
            ledger.DEFAULT_CHECKPOINT_PATH = original_default
            ledger.LEGACY_CHECKPOINT_PATH = original_legacy


def _extract_run_bridge(checkpoint_error_type, checkpoint_exists_fn):
    tree = ast.parse(BRIDGE_PATH.read_text())
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'run_bridge'
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)

    events = {'server_constructed': False}

    class MatrixStub:
        def start(self):
            return None
        def wait_ready(self, timeout=5.0):
            return True
        def stop(self):
            return None

    class HTTPServerStub:
        def __init__(self, *_args, **_kwargs):
            events['server_constructed'] = True
        def serve_forever(self):
            return None

    class GateStub:
        def seal(self):
            return None

    ns = {
        'os': os,
        'json': json,
        '_register_handlers': lambda: None,
        'matrix': MatrixStub(),
        'checkpoint_exists': checkpoint_exists_fn,
        'load_checkpoint': lambda _matrix: {},
        'CheckpointError': checkpoint_error_type,
        'HTTPServer': HTTPServerStub,
        'BridgeHandler': object,
        'gate': GateStub(),
        'save_checkpoint': lambda _matrix: None,
        'print': lambda *args, **kwargs: None,
    }
    exec(compile(module, str(BRIDGE_PATH), 'exec'), ns)
    return ns['run_bridge'], events


def test_bridge_never_becomes_ready_when_legacy_namespace_is_detected():
    ledger = _load_ledger()

    def detect_legacy():
        raise ledger.CheckpointError('legacy v1 checkpoint requires explicit migration')

    run_bridge, events = _extract_run_bridge(ledger.CheckpointError, detect_legacy)
    try:
        run_bridge(7890)
        propagated = False
    except ledger.CheckpointError:
        propagated = True

    _check('legacy namespace rejection propagates before restore try-block', propagated)
    _check('HTTP server is not constructed after legacy detection', not events['server_constructed'])


if __name__ == '__main__':
    print('AEGIS M1 checkpoint v2 migration')
    test_checkpoint_v2_schema_and_geometry_binding()
    test_legacy_v1_checkpoint_is_rejected()
    test_versioned_default_namespace_detects_legacy_checkpoint()
    test_bridge_never_becomes_ready_when_legacy_namespace_is_detected()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
