#!/usr/bin/env python3
"""Reproducible OFFLINE simulated-latency source-plane benchmark (zero tokens/keys/network).

Compares independent in-memory clients with one shared single-flight client.
All reported timings are synthetic-transport measurements, NOT GitHub/API/network
or production Pando/Scion throughput claims. No CI performance threshold.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import importlib.util
import json
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'harness/sdk/source_plane.py'
spec = importlib.util.spec_from_file_location('aegis_source_plane_bench', MODULE)
assert spec and spec.loader
sp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sp
spec.loader.exec_module(sp)


class PreFixSharedCache(sp.SourcePlane):
    """Historical V1.2 cache behavior, reconstructed solely for benchmark control.

    Reads are cached after completion, but concurrent same-key misses are not
    coordinated. This is a benchmark-only comparison, not production code.
    """

    def _get(self, api_path):
        cached = self._api_cache.get(api_path)
        if cached is not None:
            return cached
        raw = self.transport(api_path, self.token)
        if len(raw) > sp.MAX_JSON_BYTES:
            raise sp.SourcePlaneError('API response exceeds safe size limit')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise sp.SourcePlaneError('GitHub API returned non-object')
        self._api_cache[api_path] = value
        return value


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()


def build_fixture(root: Path, count: int) -> tuple[str, dict[str, Path]]:
    repo = root / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.email', 'benchmark@example.invalid')
    git(repo, 'config', 'user.name', 'AEGIS Source Plane')
    docs = repo / 'docs'
    docs.mkdir()
    for n in range(count):
        (docs / f'file{n}.txt').write_text(f'object:{n}\n', encoding='utf-8')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'benchmark fixture')
    return git(repo, 'rev-parse', 'HEAD'), {'Aegis-Omega/AEGIS-OMEGA': repo}


def sample(mapping, sha: str, *, n_tasks: int, n_files: int, workers: int, delay_s: float, shared: bool, legacy: bool = False):
    native = sp.LocalGitTransport(mapping)
    counts = collections.Counter()
    lock = threading.Lock()
    in_flight = 0
    peak = 0

    def slow_transport(path, token):
        nonlocal in_flight, peak
        with lock:
            counts[path] += 1
            in_flight += 1
            peak = max(peak, in_flight)
        try:
            time.sleep(delay_s)
            return native(path, token)
        finally:
            with lock:
                in_flight -= 1

    requests = [sp.ArtifactRequest('Aegis-Omega/AEGIS-OMEGA', sha, f'docs/file{i % n_files}.txt')
                for i in range(n_tasks)]
    single = (PreFixSharedCache(transport=slow_transport) if legacy else sp.SourcePlane(transport=slow_transport)) if shared else None

    def work(req):
        plane = single or sp.SourcePlane(transport=slow_transport)
        return plane.artifact(req)

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(work, requests))
    elapsed = time.perf_counter() - started
    assert len(results) == n_tasks
    assert all(result['verification'] == 'GIT_BLOB_SHA1_MATCH' for result in results)
    # Every independent client sees exact same immutable object for same file.
    assert all(results[i] == results[i % n_files] for i in range(n_tasks))
    return {'elapsed_ms': round(elapsed * 1000, 2), 'backend_calls': sum(counts.values()),
            'unique_git_objects': len(counts), 'max_concurrent_transport_calls': peak}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--files', type=int, default=6)
    ap.add_argument('--tasks', type=int, default=32)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--latency-ms', type=float, default=8.0)
    ap.add_argument('--trials', type=int, default=3)
    args = ap.parse_args(argv)
    if not (1 <= args.files <= 24 and 1 <= args.files <= args.tasks <= 128 and
            1 <= args.workers <= 32 and 0 <= args.latency_ms <= 50 and 1 <= args.trials <= 10):
        ap.error('bounded local benchmark limits exceeded')
    output = {'kind': 'AEGIS_SOURCE_PLANE_SIMULATED_LATENCY_BENCH_V1',
              'scope': 'OFFLINE_GIT; SYNTHETIC_TRANSPORT_DELAY; NOT_PRODUCTION',
              'parameters': vars(args), 'cases': {}}
    with tempfile.TemporaryDirectory() as tmp:
        sha, mapping = build_fixture(Path(tmp), args.files)
        output['fixture_commit'] = sha
        for name, n_files, shared in [
            ('independent_clients_repeated_file', 1, False),
            ('pre_fix_shared_cache_repeated_file', 1, True),
            ('shared_singleflight_repeated_file', 1, True),
            ('shared_singleflight_distinct_files', args.files, True),
        ]:
            samples = [sample(mapping, sha, n_tasks=args.tasks, n_files=n_files,
                              workers=args.workers, delay_s=args.latency_ms / 1000,
                              shared=shared, legacy=(name == 'pre_fix_shared_cache_repeated_file'))
                       for _ in range(args.trials)]
            output['cases'][name] = {'median_elapsed_ms': round(statistics.median(s['elapsed_ms'] for s in samples), 2),
                                     'backend_calls_each_trial': [s['backend_calls'] for s in samples],
                                     'unique_git_objects_each_trial': [s['unique_git_objects'] for s in samples],
                                     'max_concurrent_transport_calls': max(s['max_concurrent_transport_calls'] for s in samples)}
        baseline = output['cases']['independent_clients_repeated_file']['median_elapsed_ms']
        shared = output['cases']['shared_singleflight_repeated_file']['median_elapsed_ms']
        output['simulated_median_speedup_vs_independent_clients'] = round(baseline / shared, 2) if shared else None
        old_shared = output['cases']['pre_fix_shared_cache_repeated_file']['median_elapsed_ms']
        output['simulated_median_speedup_vs_pre_fix_shared_cache'] = round(old_shared / shared, 2) if shared else None
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
