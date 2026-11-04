#!/usr/bin/env python3
"""Offline contract tests for plugging into canonical repository_knowledge API.

Uses a schema-compatible fake for the boundary only. The real AEGIS module
must be run in the GitHub source tree for integration admission.
"""
from __future__ import annotations
import copy
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

P = Path(__file__).resolve().parents[1] / 'harness/sdk/source_plane.py'
spec = importlib.util.spec_from_file_location('aegis_source_plane_bridge', P)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

STUB = '''
import subprocess
from pathlib import Path

def _git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args]).decode().strip()

def build_snapshot(root, *, repository_id, repository_full_name=None):
    head = _git(root, 'rev-parse', 'HEAD')
    tree = _git(root, 'rev-parse', 'HEAD^{tree}')
    raw = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-r', '-z', 'HEAD'])
    entries = []
    for row in raw.split(b'\\x00'):
        if not row:
            continue
        left, path = row.decode().split('\\t', 1)
        mode, kind, oid = left.split(' ')
        entries.append({'path': path, 'object_sha': oid, 'mode': mode})
    return dict(source_head_sha=head, source_tree_sha=tree, artifacts=entries)

def verify_snapshot(root, snapshot, *, expected_repository_id=None):
    return {'status': 'ESTABLISHED' if _git(root, 'rev-parse', 'HEAD') == snapshot['source_head_sha'] else 'DENIED'}
'''

class BridgeContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL).decode().strip()
        self.git = git
        git('init', '-q')
        git('config', 'user.name', 'Aegis Bridge')
        git('config', 'user.email', 'aegis@example.invalid')
        (self.repo / 'data.txt').write_text('verified bytes\n')
        git('add', '.')
        git('commit', '-qm', 'init')
        self.head = git('rev-parse', 'HEAD')
        self.repo_name = 'Aegis-Omega/AEGIS-OMEGA'
        self.mapping = {self.repo_name: self.repo}
        self.manifest = mod.SourcePlane(transport=mod.LocalGitTransport(self.mapping)).manifest(
            [mod.ArtifactRequest(self.repo_name, self.head, 'data.txt')]
        )
        self.fake_sdk = self.root / 'sdk'
        self.fake_sdk.mkdir()
        (self.fake_sdk / 'repository_knowledge.py').write_text(STUB)

    def test_fails_closed_without_canonical_module(self):
        with patch.object(mod, '__file__', str(self.root / 'missing_sdk' / 'source_plane.py')):
            with self.assertRaisesRegex(mod.SourcePlaneError, 'repository_knowledge module missing'):
                mod.verify_local_repository_binding(self.manifest, self.mapping)

    def test_matches_interface_and_actual_local_git_bytes(self):
        with patch.object(mod, '__file__', str(self.fake_sdk / 'source_plane.py')):
            receipt = mod.verify_local_repository_binding(self.manifest, self.mapping)
        self.assertEqual(receipt, {'status': 'ESTABLISHED', 'reason_codes': [], 'authority': 'NONE'})

    def test_denies_forged_digest_even_with_recomputed_manifest_hash(self):
        forged = copy.deepcopy(self.manifest)
        forged['artifacts'][0]['content_sha256'] = '0' * 64
        unsigned = {k:v for k,v in forged.items() if k != 'manifest_sha256'}
        forged['manifest_sha256'] = mod.canonical_sha256({'domain': mod.SCHEMA_VERSION, 'payload': unsigned})
        with patch.object(mod, '__file__', str(self.fake_sdk / 'source_plane.py')):
            receipt = mod.verify_local_repository_binding(forged, self.mapping)
        self.assertEqual(receipt['status'], 'DENIED')
        self.assertTrue(any(s.startswith('ARTIFACT_CONTENT_MISMATCH:') for s in receipt['reason_codes']))

    def test_denies_stale_commit_head(self):
        (self.repo / 'second.txt').write_text('new\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'move')
        with patch.object(mod, '__file__', str(self.fake_sdk / 'source_plane.py')):
            receipt = mod.verify_local_repository_binding(self.manifest, self.mapping)
        self.assertEqual(receipt['status'], 'DENIED')
        self.assertIn('SOURCE_HEAD_MISMATCH:Aegis-Omega/AEGIS-OMEGA', receipt['reason_codes'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
