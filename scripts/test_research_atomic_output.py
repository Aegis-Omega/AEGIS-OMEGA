"""Fail-closed publication of completed research evidence, never half a JSON file."""
from __future__ import annotations

import contextlib
import concurrent.futures
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import research_collector as rc
from test_research_collector import capture


class AtomicOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'capture.json'
        self.encoded = '{"status":"COMPLETED","content":"' + ('x' * 4000) + '"}\n'

    def remains_clean(self):
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.root.glob('.aegis-capture-*.partial')), [])

    def test_complete_file_is_created_after_full_write(self):
        rc._publish_complete_result(str(self.out), self.encoded)
        self.assertEqual(self.out.read_text(), self.encoded)
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.root.glob('.aegis-capture-*.partial')), [])

    def test_partial_write_failure_leaves_no_output_or_staging(self):
        actual_fdopen = os.fdopen
        class BrokenWriter:
            def __init__(self, wrapped): self.f = wrapped
            def __enter__(self): self.f.__enter__(); return self
            def __exit__(self, *exc): return self.f.__exit__(*exc)
            def write(self, data):
                self.f.write(data[:9]);self.f.flush()
                raise OSError('SIMULATED_DISK_FULL')
        def fdopen(*args, **kwargs):
            return BrokenWriter(actual_fdopen(*args, **kwargs))
        with patch.object(rc.os, 'fdopen', side_effect=fdopen):
            with self.assertRaisesRegex(OSError, 'SIMULATED_DISK_FULL'):
                rc._publish_complete_result(str(self.out), self.encoded)
        self.remains_clean()

    def test_file_fsync_failure_before_publication_denied(self):
        with patch.object(rc.os, 'fsync', side_effect=OSError('SIMULATED_SYNC_FAILURE')):
            with self.assertRaisesRegex(OSError, 'SIMULATED_SYNC_FAILURE'):
                rc._publish_complete_result(str(self.out), self.encoded)
        self.remains_clean()

    def test_file_exists_no_overwrite_no_temp_leak(self):
        self.out.write_text('ORIGINAL')
        with self.assertRaises(FileExistsError):
            rc._publish_complete_result(str(self.out), self.encoded)
        self.assertEqual(self.out.read_text(), 'ORIGINAL')
        self.assertEqual(list(self.root.glob('.aegis-capture-*.partial')), [])

    def test_symlink_output_is_not_followed_or_overwritten(self):
        victim = self.root / 'victim';victim.write_text('KEEP_ME')
        self.out.symlink_to(victim)
        with self.assertRaises(FileExistsError):
            rc._publish_complete_result(str(self.out), self.encoded)
        self.assertEqual(victim.read_text(), 'KEEP_ME')
        self.assertEqual(list(self.root.glob('.aegis-capture-*.partial')), [])

    def test_hard_link_error_fails_closed(self):
        with patch.object(rc.os, 'link', side_effect=OSError('LINK_UNAVAILABLE')):
            with self.assertRaisesRegex(OSError, 'LINK_UNAVAILABLE'):
                rc._publish_complete_result(str(self.out), self.encoded)
        self.remains_clean()

    def test_simultaneous_publishers_exactly_one_wins(self):
        def compete(i):
            try:
                rc._publish_complete_result(str(self.out), self.encoded.replace('COMPLETED',f'READY{i}'))
                return True
            except FileExistsError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(compete, range(12)))
        self.assertEqual(sum(results),1)
        self.assertEqual(list(self.root.glob('.aegis-capture-*.partial')), [])
        self.assertTrue(json.loads(self.out.read_text())['status'].startswith('READY'))

    def test_public_cli_handles_publication_failure_with_no_artifact(self):
        with patch.object(rc, '_run_bounded_worker', return_value=capture()), \
             patch.object(rc, '_publish_complete_result', side_effect=OSError('FULL_DISK')):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as raised:
                    rc.main(['https://docs.example.org/page','--allow-host','docs.example.org',
                             '--allow-network','--output',str(self.out)])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn('OUTPUT_PUBLICATION_FAILED',err.getvalue())
        self.remains_clean()

if __name__=='__main__': unittest.main()
