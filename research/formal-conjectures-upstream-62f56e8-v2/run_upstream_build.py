#!/usr/bin/env python3
"""Build the pinned metadata-only Formal Conjectures patch in an isolated copy.

Python 3.10+, Git, and Lake/Lean (normally via elan) are required. This program
never pushes, submits a PR, changes the source checkout, or replays the external
proof. A successful module build is not a proof of its sorry-bearing statements.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

BASE = '62f56e8e4dab933a720f649721875c478b0ecf1c'
REPOSITORY = 'https://github.com/google-deepmind/formal-conjectures.git'
TARGET = 'FormalConjectures/Wikipedia/Transcendental.lean'
MODULE = 'FormalConjectures.Wikipedia.Transcendental'
TOOLCHAIN = 'leanprover/lean4:v4.33.1'
MATHLIB = '0df444a360eaa60ab8c11dca51a86af692955474'
MATHLIB_URL = 'https://github.com/leanprover-community/mathlib4'
BLOBS = {
    TARGET: 'd937702e70bad07610b620d74a1ff97223802e25',
    'lean-toolchain': 'a8afa7d1b02d96f0671eba854a8dc4b416beb473',
    'lake-manifest.json': 'fae5d498d3f9dc3f6d1efd7c2adc03dd5bb6c8d6',
}
PATCH_SHA256 = '0f7fc5bee7ee5b0c8693c95d493f0cc5a7b20c9ecf5d8b747780cf010dcd1f67'
PROOF_URL = ('https://github.com/Aegis-Omega/AEGIS-OMEGA/blob/'
             'ffcdea96a550b03d5a2ff6e11c91ca0c295681ca/'
             'research/formal-conjectures-pilot/ExpTranscendence.lean#L149-L153')
ANCHOR = b'@[category textbook, AMS 11]\ntheorem exp_add_pi_or_exp_add_mul_transcendental :'
ANNOTATION = ('@[category textbook, AMS 11,\n  formal_proof using lean4 at\n    "' + PROOF_URL + '"]\n').encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f'{label}: expected {expected!r}; got {actual!r}')


def check_patch(data: bytes) -> None:
    require_equal(sha256(data), PATCH_SHA256, 'original patch SHA-256')


def patched_bytes(before: bytes) -> bytes:
    require_equal(before.count(ANCHOR), 1, 'unique textbook theorem anchor')
    replacement = ANNOTATION + ANCHOR.split(b'\n', 1)[1]
    return before.replace(ANCHOR, replacement, 1)


def check_version(text: str) -> None:
    versions = re.findall(r'^Lean \(version ([^,\s)]+)', text, flags=re.MULTILINE)
    require_equal(versions, ['4.33.1'], 'runtime Lean version')


def check_manifest(data: bytes) -> None:
    doc = json.loads(data)
    if not isinstance(doc, dict) or not isinstance(doc.get('packages'), list):
        raise ValueError('manifest has no packages list')
    packages = doc['packages']
    if not all(isinstance(item, dict) for item in packages):
        raise ValueError('malformed package entry')
    matches = [item for item in packages if item.get('name') == 'mathlib']
    require_equal(len(matches), 1, 'unique mathlib dependency')
    for key, value in {'type': 'git', 'url': MATHLIB_URL, 'rev': MATHLIB}.items():
        require_equal(matches[0].get(key), value, 'mathlib ' + key)


def object_digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ValueError('missing, empty, or symlinked output object: ' + str(path))
    return sha256(path.read_bytes())


def new_receipt() -> dict:
    return {
        'schema': 'AEGIS_FC_UPSTREAM_MODULE_BUILD_V1',
        'status': 'NOT_RUN', 'upstream_module_build': 'NOT_RUN',
        'external_proof_replay': 'NOT_RUN', 'authority_effect': 'NONE',
        'public_submission': False, 'remote_writes': False,
        'base_sha': BASE, 'module': MODULE, 'toolchain': TOOLCHAIN,
        'mathlib_sha': MATHLIB, 'proof_url': PROOF_URL,
        'base_file_git_blobs': dict(BLOBS),
        'scope': 'Metadata-only module build; not a proof of the module statements.',
        'commands': [],
    }


class BlockedError(RuntimeError):
    """An execution prerequisite is unavailable."""


class Recorder:
    def __init__(self, out: Path, receipt: dict, timeout: int):
        self.out, self.receipt, self.timeout = out, receipt, timeout
        self.env = os.environ.copy()
        for key in ('LEAN_PATH', 'LEAN_SRC_PATH', 'LEAN_SYSROOT',
                    'LAKE_OVERRIDE_LEAN', 'ELAN_TOOLCHAIN'):
            self.env.pop(key, None)
        (out / 'logs').mkdir()

    def save(self) -> None:
        tmp = self.out / 'receipt.json.tmp'
        tmp.write_text(json.dumps(self.receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        tmp.replace(self.out / 'receipt.json')

    def run(self, name: str, args: list[str], cwd: Path | None = None) -> str:
        log_path = self.out / 'logs' / (name + '.log')
        entry = {'step': name, 'argv': args, 'cwd': str(cwd) if cwd else None,
                 'exit_code': None, 'outcome': 'RUNNING', 'log': str(log_path.relative_to(self.out))}
        self.receipt['commands'].append(entry)
        self.save()
        print(f'[{name}]', flush=True)
        try:
            with log_path.open('wb') as log:
                result = subprocess.run(args, cwd=cwd, env=self.env, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=self.timeout, check=False)
            entry.update(exit_code=result.returncode, outcome='COMPLETED')
        except subprocess.TimeoutExpired:
            entry['outcome'] = 'TIMEOUT'
            raise RuntimeError(f'{name}: timeout; see {log_path}')
        except OSError as exc:
            entry['outcome'] = 'SPAWN_FAILED'
            raise BlockedError(f'{name}: {exc}') from exc
        finally:
            if log_path.is_file():
                entry['log_sha256'] = sha256(log_path.read_bytes())
            self.save()
        if result.returncode != 0:
            raise RuntimeError(f'{name}: exit {result.returncode}; see {log_path}')
        return log_path.read_text(encoding='utf-8', errors='replace').strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='New output directory; never overwritten.')
    parser.add_argument('--checkout', type=Path, help='Existing local upstream repo; clone its committed objects, not its working tree.')
    parser.add_argument('--timeout', type=int, default=1800, help='Per-command timeout in seconds.')
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    out = args.out.expanduser().resolve()
    if args.checkout is not None and out.is_relative_to(args.checkout.expanduser().resolve()):
        print('Refusing output inside the source checkout.', file=sys.stderr)
        return 2
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f'Refusing output directory: {exc}', file=sys.stderr)
        return 2
    receipt = new_receipt()
    receipt.update(started_at_utc=datetime.now(timezone.utc).isoformat(),
                   runner_sha256=sha256(Path(__file__).read_bytes()))
    rec = Recorder(out, receipt, args.timeout)
    rec.save()
    code = 1
    try:
        patch = Path(__file__).resolve().with_name('formal-proof-link.patch')
        check_patch(patch.read_bytes())
        receipt['patch_sha256'] = PATCH_SHA256
        missing = [name for name in ('git', 'lake') if shutil.which(name) is None]
        if missing:
            raise BlockedError('Missing executable(s): ' + ', '.join(missing))
        receipt['status'] = 'RUNNING'
        rec.save()
        repo = out / 'checkout'
        if args.checkout is not None:
            source = args.checkout.expanduser().resolve()
            if not source.is_dir():
                raise BlockedError('Local repository directory does not exist')
            rec.run('clone-local', ['git', 'clone', '--no-hardlinks', '--no-checkout', '--', str(source), str(repo)])
            checkout_ref = BASE
        else:
            rec.run('init', ['git', 'init', str(repo)])
            rec.run('fetch-pinned', ['git', 'fetch', '--depth=1', REPOSITORY, BASE], repo)
            checkout_ref = 'FETCH_HEAD'
        rec.run('checkout', ['git', '-c', 'advice.detachedHead=false', 'checkout', '--detach', checkout_ref], repo)
        require_equal(rec.run('head-before', ['git', 'rev-parse', 'HEAD'], repo), BASE, 'checkout HEAD')
        require_equal(rec.run('clean-before', ['git', 'status', '--porcelain'], repo), '', 'initial working tree')
        originals = {name: (repo / name).read_bytes() for name in BLOBS}
        for name, blob in BLOBS.items():
            require_equal(git_blob(originals[name]), blob, 'base blob: ' + name)
        require_equal(originals['lean-toolchain'].decode().strip(), TOOLCHAIN, 'toolchain file')
        check_manifest(originals['lake-manifest.json'])
        expected = patched_bytes(originals[TARGET])
        rec.run('patch-check', ['git', 'apply', '--check', '--whitespace=error-all', str(patch)], repo)
        rec.run('patch-apply', ['git', 'apply', '--whitespace=error-all', str(patch)], repo)
        require_equal((repo / TARGET).read_bytes(), expected, 'metadata-only modified file')
        receipt['patched_source_sha256'] = sha256(expected)
        receipt['patched_source_git_blob'] = git_blob(expected)
        rec.run('patch-reverse-check', ['git', 'apply', '--reverse', '--check', str(patch)], repo)
        version = rec.run('lean-version', ['lake', 'env', 'lean', '--version'], repo)
        check_version(version)
        receipt['observed_lean_version'] = version
        rec.run('cache-get', ['lake', 'exe', 'cache', 'get'], repo)
        require_equal(rec.run('mathlib-head-before', ['git', 'rev-parse', 'HEAD'], repo / '.lake/packages/mathlib'), MATHLIB, 'materialized mathlib')
        require_equal(rec.run('mathlib-clean-before', ['git', 'status', '--porcelain', '--untracked-files=no'], repo / '.lake/packages/mathlib'), '', 'mathlib tracked source before build')
        for name in ('lean-toolchain', 'lake-manifest.json'):
            require_equal((repo / name).read_bytes(), originals[name], 'dependency pin after cache: ' + name)
        obj = repo / '.lake/build/lib/lean/FormalConjectures/Wikipedia/Transcendental.olean'
        # This path is inside the newly created isolated copy, never the source checkout.
        if obj.exists() or obj.is_symlink():
            obj.unlink()
        receipt['upstream_module_build'] = 'RUNNING'
        rec.save()
        rec.run('upstream-build', ['lake', '--wfail', 'build', MODULE], repo)
        require_equal((repo / TARGET).read_bytes(), expected, 'source after build')
        for name in ('lean-toolchain', 'lake-manifest.json'):
            require_equal((repo / name).read_bytes(), originals[name], 'dependency pin after build: ' + name)
        require_equal(rec.run('head-after', ['git', 'rev-parse', 'HEAD'], repo), BASE, 'final HEAD')
        require_equal(rec.run('mathlib-head-after', ['git', 'rev-parse', 'HEAD'], repo / '.lake/packages/mathlib'), MATHLIB, 'final mathlib')
        require_equal(rec.run('mathlib-clean-after', ['git', 'status', '--porcelain', '--untracked-files=no'], repo / '.lake/packages/mathlib'), '', 'mathlib tracked source after build')
        require_equal(rec.run('diff-scope', ['git', 'diff', '--name-only', 'HEAD'], repo), TARGET, 'changed tracked files')
        rec.run('diff-check', ['git', 'diff', '--check'], repo)
        receipt['module_object_sha256'] = object_digest(obj)
        receipt['module_object'] = str(obj.relative_to(out))
        receipt.update(status='PASS', upstream_module_build='PASS')
        code = 0
    except BlockedError as exc:
        receipt.update(status='BLOCKED', error=str(exc))
        code = 2
    except (ValueError, RuntimeError, OSError, UnicodeError, KeyboardInterrupt) as exc:
        receipt.update(status='FAILED', error=str(exc) or type(exc).__name__)
    finally:
        if receipt['upstream_module_build'] == 'RUNNING':
            receipt['upstream_module_build'] = 'FAIL'
        receipt['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        rec.save()
    print(json.dumps({key: receipt[key] for key in ('status', 'upstream_module_build', 'external_proof_replay')}, indent=2))
    if 'error' in receipt:
        print(receipt['error'], file=sys.stderr)
    print('Receipt: ' + str(out / 'receipt.json'))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
