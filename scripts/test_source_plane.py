#!/usr/bin/env python3
"""Offline fail-closed contract tests for AEGIS Source Plane v1."""
from __future__ import annotations

import base64
import copy
import importlib.util
import json
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'harness/sdk/source_plane.py'
spec = importlib.util.spec_from_file_location('aegis_source_plane', MODULE_PATH)
assert spec and spec.loader
import sys
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class Fixture:
    def __init__(self, repo: str = 'Aegis-Omega/AEGIS-OMEGA') -> None:
        self.repo = repo
        self.head = 'a' * 40
        self.root = 'b' * 40
        self.subtree = 'c' * 40
        self.data = b'# AEGIS source plane\n'
        self.blob = mod.git_blob_oid(self.data)
        self.calls = []
        prefix = f'/repos/{repo}'
        self.commit_path = prefix + '/git/commits/' + self.head
        self.root_path = prefix + '/git/trees/' + self.root
        self.subtree_path = prefix + '/git/trees/' + self.subtree
        self.blob_path = prefix + '/git/blobs/' + self.blob
        self.routes = {
            self.commit_path: {'sha': self.head, 'tree': {'sha': self.root}},
            self.root_path: {
                'sha': self.root, 'truncated': False, 'tree': [
                    {'path': 'docs', 'type': 'tree', 'sha': self.subtree, 'mode': '040000'}]},
            self.subtree_path: {
                'sha': self.subtree, 'tree': [
                    {'path': 'README.md', 'type': 'blob', 'sha': self.blob, 'mode': '100644'},
                    {'path': 'AGENT.md', 'type': 'blob', 'sha': self.blob, 'mode': '100644'}]},
            self.blob_path: {'sha': self.blob, 'encoding': 'base64', 'size': len(self.data),
                             'content': base64.b64encode(self.data).decode('ascii')},
        }

    def transport(self, path: str, token: str | None) -> bytes:
        self.calls.append(path)
        if path not in self.routes:
            raise mod.SourcePlaneError('unavailable route')
        return json.dumps(self.routes[path]).encode('utf-8')

    def request(self, name: str = 'README.md'):
        return mod.ArtifactRequest(self.repo, self.head, 'docs/' + name)


class SourcePlaneContract(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.plane = mod.SourcePlane(transport=self.fixture.transport)

    def test_sparse_read_exact_commit_and_git_object_integrity(self):
        receipt = self.plane.artifact(self.fixture.request())
        self.assertEqual(receipt['commit_sha'], self.fixture.head)
        self.assertEqual(receipt['tree_sha'], self.fixture.root)
        self.assertEqual(receipt['blob_sha1'], self.fixture.blob)
        self.assertEqual(receipt['content_sha256'], mod.hashlib.sha256(self.fixture.data).hexdigest())
        self.assertEqual(receipt['verification'], 'GIT_BLOB_SHA1_MATCH')
        self.assertEqual(len(self.fixture.calls), 4)
        self.assertTrue(all('/git/' in call for call in self.fixture.calls))

    def test_dedup_and_deterministic_federated_manifest(self):
        requests = [self.fixture.request('README.md'), self.fixture.request('AGENT.md'),
                    self.fixture.request('README.md')]
        first = self.plane.manifest(requests)
        second = self.plane.manifest(list(reversed(requests)))
        self.assertEqual(first, second)
        self.assertEqual(mod.verify_manifest_document(first)["status"], "ESTABLISHED")
        self.assertEqual(len(first['artifacts']), 2)
        self.assertEqual(first['authority'], 'NONE')
        self.assertEqual(self.fixture.calls.count(self.fixture.blob_path), 1)
        digest = first['manifest_sha256']
        unsigned = dict(first)
        unsigned.pop('manifest_sha256')
        self.assertEqual(digest, mod.canonical_sha256({'domain': mod.SCHEMA_VERSION,
                                                       'payload': unsigned}))

    def test_tampered_manifest_document_denied(self):
        manifest = self.plane.manifest([self.fixture.request()])
        tampered = copy.deepcopy(manifest)
        tampered['artifacts'][0]['content_sha256'] = '0' * 64
        result = mod.verify_manifest_document(tampered)
        self.assertEqual(result['status'], 'DENIED')
        self.assertIn('MANIFEST_DIGEST_MISMATCH', result['reason_codes'])

    def test_trust_claim_is_not_enough_for_authority(self):
        manifest = self.plane.manifest([self.fixture.request()])
        manifest['authority'] = 'WRITE'
        manifest['manifest_sha256'] = mod.canonical_sha256(
            {'domain': mod.SCHEMA_VERSION,
             'payload': {k: v for k, v in manifest.items() if k != 'manifest_sha256'}})
        result = mod.verify_manifest_document(manifest)
        self.assertEqual(result['status'], 'DENIED')
        self.assertIn('INVALID_AUTHORITY', result['reason_codes'])

    def test_commit_mutation_denied(self):
        self.fixture.routes[self.fixture.commit_path]['sha'] = 'd' * 40
        with self.assertRaisesRegex(mod.SourcePlaneError, 'commit SHA'):
            self.plane.artifact(self.fixture.request())

    def test_tree_mutation_and_truncation_denied(self):
        self.fixture.routes[self.fixture.root_path]['truncated'] = True
        with self.assertRaisesRegex(mod.SourcePlaneError, 'truncated'):
            self.plane.artifact(self.fixture.request())
        self.fixture.routes[self.fixture.root_path]['truncated'] = False
        self.fixture.routes[self.fixture.root_path]['sha'] = '0' * 40
        with self.assertRaisesRegex(mod.SourcePlaneError, 'tree identity'):
            mod.SourcePlane(transport=self.fixture.transport).artifact(self.fixture.request())

    def test_blob_tampering_denied(self):
        forged = b'forged'
        self.fixture.routes[self.fixture.blob_path]['size'] = len(forged)
        self.fixture.routes[self.fixture.blob_path]['content'] = base64.b64encode(forged).decode()
        with self.assertRaisesRegex(mod.SourcePlaneError, 'hash verification'):
            self.plane.artifact(self.fixture.request())

    def test_invalid_encoding_denied(self):
        self.fixture.routes[self.fixture.blob_path]['content'] = '@@@=='
        with self.assertRaisesRegex(mod.SourcePlaneError, 'base64'):
            self.plane.artifact(self.fixture.request())

    def test_large_blob_denied(self):
        self.fixture.routes[self.fixture.blob_path]['size'] = mod.MAX_BLOB_BYTES + 1
        with self.assertRaisesRegex(mod.SourcePlaneError, 'too large'):
            self.plane.artifact(self.fixture.request())

    def test_submodule_and_nonblob_denied(self):
        self.fixture.routes[self.fixture.subtree_path]['tree'][0]['type'] = 'commit'
        with self.assertRaisesRegex(mod.SourcePlaneError, 'not an ordinary Git blob'):
            self.plane.artifact(self.fixture.request())

    def test_invalid_path_ref_and_repo_fail_closed(self):
        for path in ('/etc/passwd', '../other', 'docs/../README.md', 'docs//README.md',
                     'docs/./README.md', 'docs\\README.md', ''):
            with self.subTest(path=path), self.assertRaises(mod.SourcePlaneError):
                mod.ArtifactRequest(self.fixture.repo, self.fixture.head, path)
        for repo in ('../repo', 'owner/repo/other', 'https://evil.com/repo'):
            with self.subTest(repo=repo), self.assertRaises(mod.SourcePlaneError):
                mod.ArtifactRequest(repo, self.fixture.head, 'README.md')
        with self.assertRaises(mod.SourcePlaneError):
            mod.ArtifactRequest(self.fixture.repo, 'main', 'README.md')

    def test_missing_path_denied(self):
        with self.assertRaisesRegex(mod.SourcePlaneError, 'not found'):
            self.plane.artifact(self.fixture.request('MISSING.md'))

    def test_manifest_bound_and_malformed_spec_denied(self):
        with self.assertRaises(mod.SourcePlaneError):
            self.plane.manifest([])
        with self.assertRaises(mod.SourcePlaneError):
            self.plane.manifest([self.fixture.request()] * 101)
        with self.assertRaises(mod.SourcePlaneError):
            mod.parse_artifact('owner/repo@main:README.md')

    def test_cached_blob_scoped_to_repository(self):
        alt = Fixture('Aegis-Omega/formal-conjectures')
        def transport(path, token):
            if path.startswith('/repos/' + alt.repo + '/'):
                return alt.transport(path, token)
            return self.fixture.transport(path, token)
        plane = mod.SourcePlane(transport=transport)
        result = plane.manifest([self.fixture.request(), alt.request()])
        self.assertEqual(len(result['artifacts']), 2)
        self.assertEqual(self.fixture.calls.count(self.fixture.blob_path), 1)
        self.assertEqual(alt.calls.count(alt.blob_path), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
