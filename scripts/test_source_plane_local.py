#!/usr/bin/env python3
"""Full real-Git object-store integration tests (no network or new GitHub repo)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / 'harness/sdk/source_plane.py'
spec = importlib.util.spec_from_file_location('aegis_source_plane_local', MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def git(root: Path, *args: str) -> str:
    p = subprocess.run(['git', '-C', str(root), *args], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout.decode().strip()


def init_repository(root: Path, content: str) -> str:
    root.mkdir(parents=True, exist_ok=True)
    git(root, 'init', '-q')
    git(root, 'config', 'user.email', 'source-plane@example.invalid')
    git(root, 'config', 'user.name', 'Source Plane Contract')
    (root / 'docs').mkdir()
    (root / 'docs' / 'README.md').write_text(content, encoding='utf-8')
    (root / 'file.txt').write_text('original\n', encoding='utf-8')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')
    return git(root, 'rev-parse', 'HEAD')


class LocalGitContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.a = self.base / 'main'
        self.b = self.base / 'formal'
        self.head_a = init_repository(self.a, 'Aegis Ω | one\n')
        self.head_b = init_repository(self.b, 'Lean 4 formal target\n')
        self.mapping = {'Aegis-Omega/AEGIS-OMEGA': self.a,
                        'Aegis-Omega/formal-conjectures': self.b}
        self.transport = mod.LocalGitTransport(self.mapping)
        self.plane = mod.SourcePlane(transport=self.transport)

    def req(self, repo='Aegis-Omega/AEGIS-OMEGA', sha=None, path='docs/README.md'):
        return mod.ArtifactRequest(repo, sha or (self.head_b if 'formal-' in repo else self.head_a), path)

    def test_git_tree_and_blob_hashes_match_real_git(self):
        req = self.req()
        a = self.plane.artifact(req)
        self.assertEqual(a['tree_sha'], git(self.a, 'rev-parse', 'HEAD^{tree}'))
        self.assertEqual(a['blob_sha1'], git(self.a, 'rev-parse', 'HEAD:docs/README.md'))
        self.assertEqual(a['content_sha256'], hashlib.sha256('Aegis Ω | one\n'.encode()).hexdigest())
        self.assertEqual(a['verification'], 'GIT_BLOB_SHA1_MATCH')

    def test_commit_tamper_is_denied_by_exact_object_identity(self):
        # Direct transport denies commits that do not exist, not merely disjoint trees.
        with self.assertRaises(mod.SourcePlaneError):
            self.plane.artifact(self.req(sha='f' * 40))

    def test_spelling_and_hidden_paths(self):
        self.assertEqual(self.plane.artifact(self.req(path='file.txt'))['mode'], '100644')
        with self.assertRaisesRegex(mod.SourcePlaneError, 'not found'):
            self.plane.artifact(self.req(path='docs/readme.md'))

    def test_many_repositories_one_manifest(self):
        other = self.req(repo='Aegis-Omega/formal-conjectures')
        result = self.plane.manifest([other, self.req(), other])
        self.assertEqual(len(result['artifacts']), 2)
        self.assertEqual(result['authority'], 'NONE')
        self.assertEqual(mod.verify_manifest_document(result)['status'], 'ESTABLISHED')
        self.assertEqual(result, self.plane.manifest([self.req(), other]))

    def test_no_checkout_or_worktree_write(self):
        before_a = git(self.a, 'status', '--porcelain=v1')
        before_b = git(self.b, 'status', '--porcelain=v1')
        self.plane.manifest([self.req(), self.req(repo='Aegis-Omega/formal-conjectures')])
        self.assertEqual(before_a, git(self.a, 'status', '--porcelain=v1'))
        self.assertEqual(before_b, git(self.b, 'status', '--porcelain=v1'))

    def test_pinned_commit_survives_worktree_changes(self):
        before = self.plane.artifact(self.req())
        (self.a / 'docs' / 'README.md').write_text('updated uncommitted\n', encoding='utf-8')
        self.assertEqual(self.plane.artifact(self.req()), before)
        git(self.a, 'add', '.')
        git(self.a, 'commit', '-qm', 'new head')
        self.assertEqual(self.plane.artifact(self.req()), before)
        self.assertNotEqual(git(self.a, 'rev-parse', 'HEAD'), self.head_a)

    def test_fail_closed_missing_repo_or_unknown_api(self):
        for route in ('/repos/evil/repo/git/blobs/' + 'a' * 40,
                      '/repos/Aegis-Omega/AEGIS-OMEGA/contents/file',
                      '/repos/Aegis-Omega/AEGIS-OMEGA/git/refs/' + 'a' * 40,
                      '/repos/Aegis-Omega/AEGIS-OMEGA/git/blobs/../../secrets'):
            with self.subTest(route=route), self.assertRaises(mod.SourcePlaneError):
                self.transport(route, None)

    def test_denies_credentials(self):
        with self.assertRaisesRegex(mod.SourcePlaneError, 'credentials'):
            self.transport('/repos/Aegis-Omega/AEGIS-OMEGA/git/commits/' + self.head_a, 'token')

    def test_denies_bad_repository_mapping(self):
        with self.assertRaises(mod.SourcePlaneError):
            mod.LocalGitTransport({'Aegis-Omega/AEGIS-OMEGA': self.a / 'docs'})
        with self.assertRaises(mod.SourcePlaneError):
            mod.LocalGitTransport({})

    def test_symlink_not_executed_and_gitlink_denied(self):
        (self.a / 'link').symlink_to('file.txt')
        git(self.a, 'add', 'link')
        git(self.a, 'commit', '-qm', 'symlink blob')
        sha = git(self.a, 'rev-parse', 'HEAD')
        linked = self.plane.artifact(self.req(sha=sha, path='link'))
        self.assertEqual(linked['mode'], '120000')
        self.assertEqual(self.plane.blob_bytes(linked['repository'], linked['blob_sha1']), b'file.txt')

    def test_git_object_reader_explicitly_disables_lazy_network_fetch(self):
        # A promisor/partial clone can lazy-fetch missing objects via `git cat-file`.
        # A local transport must prohibit that, not merely omit `git fetch` calls.
        with patch.object(mod.subprocess, 'run', wraps=subprocess.run) as runner:
            result = mod.LocalGitTransport._git(self.a, 'cat-file', '-t', self.head_a, limit=128)
        self.assertEqual(result.strip(), b'commit')
        env = runner.call_args.kwargs.get('env', {})
        self.assertEqual(env.get('GIT_NO_LAZY_FETCH'), '1')
        self.assertEqual(env.get('GIT_OPTIONAL_LOCKS'), '0')
        self.assertEqual(env.get('GIT_TERMINAL_PROMPT'), '0')

    def test_missing_promisor_blob_is_not_lazy_fetched(self):
        # This creates a LOCAL file:// partial clone inside TemporaryDirectory.
        # Missing promised Git blob must remain missing: no silent Git fetch.
        git(self.a, 'config', 'uploadpack.allowFilter', 'true')
        partial = self.base / 'partial'
        subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--no-checkout',
                        self.a.as_uri(), str(partial)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        blob = git(self.a, 'rev-parse', 'HEAD:docs/README.md')
        guarded = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
        def has_object_without_network():
            result = subprocess.run(['git', '-C', str(partial), 'cat-file', '-e', blob],
                                    env=guarded, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            return result.returncode == 0
        self.assertFalse(has_object_without_network(), 'test needs genuinely missing promisor blob')
        plane = mod.SourcePlane(transport=mod.LocalGitTransport({'Aegis-Omega/AEGIS-OMEGA': partial}))
        with self.assertRaisesRegex(mod.SourcePlaneError, 'local Git object missing'):
            plane.artifact(self.req())
        self.assertFalse(has_object_without_network(), 'transport unexpectedly fetched missing promisor blob')

    def test_cli_local_mode_no_network(self):
        cmd = [sys.executable, str(MODULE_PATH),
               '--local-repo', f'Aegis-Omega/AEGIS-OMEGA={self.a}',
               '--artifact', f'Aegis-Omega/AEGIS-OMEGA@{self.head_a}:docs/README.md']
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        manifest = json.loads(cp.stdout)
        self.assertEqual(manifest['artifacts'][0]['commit_sha'], self.head_a)

    def test_cli_rejects_head_verification_without_repo(self):
        cp = subprocess.run([sys.executable, str(MODULE_PATH), '--verify-local-head',
                             '--artifact', f'Aegis-Omega/AEGIS-OMEGA@{self.head_a}:file.txt'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(cp.returncode, 2)
        self.assertIn('requires --local-repo', cp.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
