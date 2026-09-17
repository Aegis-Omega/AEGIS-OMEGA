"""
AEGIS M1 checkpoint v2 — deployed AEGIS_CHECKPOINT_PATH compatibility.

The checked-in Docker/compose environment still names the legacy v1 path
/app/data/aegis_checkpoint.json. V2 must interpret that exact legacy basename
as the legacy namespace and derive a separate v2 path in the same directory,
so an existing v1 checkpoint fails closed before bridge readiness.
"""

import importlib.util
import os
import pathlib
import tempfile

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


def _load_with_checkpoint_env(path: str):
    previous = os.environ.get('AEGIS_CHECKPOINT_PATH')
    os.environ['AEGIS_CHECKPOINT_PATH'] = path
    try:
        spec = importlib.util.spec_from_file_location(
            f'ledger_env_test_{abs(hash(path))}',
            LEDGER_PATH,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            os.environ.pop('AEGIS_CHECKPOINT_PATH', None)
        else:
            os.environ['AEGIS_CHECKPOINT_PATH'] = previous


def test_checked_in_legacy_env_is_mapped_to_v2_namespace():
    ledger = _load_with_checkpoint_env('/app/data/aegis_checkpoint.json')
    _check(
        'deployed legacy env remains legacy path',
        ledger.LEGACY_CHECKPOINT_PATH == '/app/data/aegis_checkpoint.json',
        ledger.LEGACY_CHECKPOINT_PATH,
    )
    _check(
        'deployed legacy env derives v2 path in same volume',
        ledger.DEFAULT_CHECKPOINT_PATH == '/app/data/aegis_checkpoint_v2.json',
        ledger.DEFAULT_CHECKPOINT_PATH,
    )


def test_legacy_file_under_deployed_env_fails_closed():
    with tempfile.TemporaryDirectory() as tmpdir:
        legacy_path = os.path.join(tmpdir, 'aegis_checkpoint.json')
        v2_path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        pathlib.Path(legacy_path).write_text('{}')
        ledger = _load_with_checkpoint_env(legacy_path)

        _check('derived v2 temp path is separate', ledger.DEFAULT_CHECKPOINT_PATH == v2_path)
        _check('legacy temp path is preserved', ledger.LEGACY_CHECKPOINT_PATH == legacy_path)
        try:
            ledger.checkpoint_exists()
            blocked = False
        except ledger.CheckpointError:
            blocked = True
        _check('legacy-only deployed state raises CheckpointError', blocked)

        pathlib.Path(v2_path).write_text('{}')
        try:
            v2_present = ledger.checkpoint_exists()
        except ledger.CheckpointError:
            v2_present = False
        _check('v2 checkpoint takes precedence after explicit migration', v2_present)


def test_explicit_v2_env_keeps_path_and_derives_legacy_sibling():
    with tempfile.TemporaryDirectory() as tmpdir:
        v2_path = os.path.join(tmpdir, 'aegis_checkpoint_v2.json')
        ledger = _load_with_checkpoint_env(v2_path)
        _check('explicit v2 env remains active path', ledger.DEFAULT_CHECKPOINT_PATH == v2_path)
        _check(
            'explicit v2 env derives legacy sibling',
            ledger.LEGACY_CHECKPOINT_PATH == os.path.join(tmpdir, 'aegis_checkpoint.json'),
        )


if __name__ == '__main__':
    print('AEGIS M1 checkpoint env compatibility v2')
    test_checked_in_legacy_env_is_mapped_to_v2_namespace()
    test_legacy_file_under_deployed_env_fails_closed()
    test_explicit_v2_env_keeps_path_and_derives_legacy_sibling()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
