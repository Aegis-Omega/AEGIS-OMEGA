#!/usr/bin/env python3
"""Bounded, offline parallel source-plane regression tests for agent-scale reads."""
from __future__ import annotations

import collections
import concurrent.futures
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'harness/sdk/source_plane.py'
spec = importlib.util.spec_from_file_location('source_plane_parallel', SOURCE)
assert spec and spec.loader
sp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sp
spec.loader.exec_module(sp)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()


class ParallelReads(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-q')
        git(self.repo, 'config', 'user.email', 'source@example.invalid')
        git(self.repo, 'config', 'user.name', 'AEGIS Benchmark')
        docs = self.repo / 'docs'
        docs.mkdir()
        for i in range(6):
            (docs / f'file{i}.txt').write_text(f'payload {i}\n', encoding='utf-8')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'baseline')
        self.sha = git(self.repo, 'rev-parse', 'HEAD')
        self.name = 'Aegis-Omega/AEGIS-OMEGA'
        self.native = sp.LocalGitTransport({self.name: self.repo})

    def request(self, n=0):
        return sp.ArtifactRequest(self.name, self.sha, f'docs/file{n}.txt')

    def test_same_object_concurrent_reads_fetch_once(self):
        lock = threading.Lock()
        calls = collections.Counter()
        def transport(path, token):
            with lock:
                calls[path] += 1
            time.sleep(0.025)  # expose race reproducibly, no real network
            return self.native(path, token)
        plane = sp.SourcePlane(transport=transport)
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(plane.artifact, [self.request()] * 32))
        self.assertTrue(all(x == results[0] for x in results))
        self.assertEqual(sum(calls.values()), 4, calls)
        self.assertTrue(all(count == 1 for count in calls.values()))

    def test_distinct_blob_reads_remain_parallel(self):
        lock = threading.Lock()
        active = 0
        peak = 0
        def transport(path, token):
            nonlocal active, peak
            if '/git/blobs/' not in path:
                return self.native(path, token)
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.04)
                return self.native(path, token)
            finally:
                with lock:
                    active -= 1
        plane = sp.SourcePlane(transport=transport)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            values = list(pool.map(plane.artifact, [self.request(i) for i in range(6)]))
        self.assertEqual(len({x['blob_sha1'] for x in values}), 6)
        self.assertGreaterEqual(peak, 2, 'lock should not serialize unrelated Git objects')

    def test_failed_shared_read_releases_waiters_and_allows_retry(self):
        lock = threading.Lock()
        attempts = collections.Counter()
        def transport(path, token):
            if '/git/blobs/' in path:
                with lock:
                    attempts[path] += 1
                    attempt = attempts[path]
                time.sleep(0.04)
                if attempt == 1:
                    raise sp.SourcePlaneError('deliberate temporary read failure')
            return self.native(path, token)
        plane = sp.SourcePlane(transport=transport)
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            futs = [pool.submit(plane.artifact, self.request()) for _ in range(12)]
            for future in futs:
                with self.assertRaisesRegex(sp.SourcePlaneError, 'temporary read failure'):
                    future.result(timeout=3)
        self.assertEqual(sum(attempts.values()), 1)
        self.assertEqual(plane.artifact(self.request())['path'], 'docs/file0.txt')
        self.assertEqual(sum(attempts.values()), 2)

    def test_repeated_source_reads_leave_repository_unmodified(self):
        before = git(self.repo, 'status', '--porcelain')
        plane = sp.SourcePlane(transport=self.native)
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            values = list(pool.map(plane.artifact, [self.request(i % 6) for i in range(60)]))
        self.assertEqual(len(values), 60)
        self.assertEqual(before, git(self.repo, 'status', '--porcelain'))
        self.assertEqual(self.sha, git(self.repo, 'rev-parse', 'HEAD'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
