"""Crash-window and no-clobber tests for POSIX receipt publication.

Deterministic injected I/O errors emulate the critical boundary without
requiring host storage to become full or fail during tests.
"""
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aegis_workpack.protocol import _write_receipt_create_only, cli


@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
                     "POSIX atomic publication only")
class AtomicReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'manifest.json').write_text('{bad-json', encoding='utf-8')
        self.target = self.root / 'receipt.json'

    def cli_export(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = cli([str(self.root), '--output', str(self.target)])
        return code, json.loads(out.getvalue())

    def assert_no_tmp(self):
        self.assertEqual(list(self.root.glob('*.workpack-tmp')), [])

    def test_prepublication_file_fsync_failure_never_publishes(self):
        with patch('aegis_workpack.protocol.os.fsync',
                   side_effect=OSError(errno.ENOSPC, 'injected disk full')):
            code, result = self.cli_export()
        self.assertEqual(code, 2)
        self.assertEqual(result['output_status'], 'NOT_WRITTEN')
        self.assertFalse(self.target.exists())
        self.assert_no_tmp()

    def test_prepublication_link_failure_never_publishes(self):
        with patch('aegis_workpack.protocol.os.link',
                   side_effect=OSError(errno.EIO, 'injected link failure')):
            code, result = self.cli_export()
        self.assertEqual(code, 2)
        self.assertEqual(result['output_status'], 'NOT_WRITTEN')
        self.assertFalse(self.target.exists())
        self.assert_no_tmp()

    def test_postpublication_directory_fsync_failure_is_truthful(self):
        with patch('aegis_workpack.protocol.os.fsync',
                   side_effect=[None, OSError(errno.EIO, 'injected dir sync failure')]):
            code, result = self.cli_export()
        self.assertEqual(code, 2)
        self.assertEqual(result['output_status'], 'WRITTEN_DURABILITY_UNVERIFIED')
        self.assertEqual(result['output_error'], 'OUTPUT_DURABILITY_UNVERIFIED')
        self.assertEqual(json.loads(self.target.read_text())['disposition'], 'NOT_ADMITTED')
        self.assert_no_tmp()

    def test_existing_output_unchanged_and_no_hidden_temp(self):
        self.target.write_bytes(b'ORIGINAL\n')
        code, result = self.cli_export()
        self.assertEqual(code, 2)
        self.assertEqual(result['output_status'], 'NOT_WRITTEN')
        self.assertEqual(self.target.read_bytes(), b'ORIGINAL\n')
        self.assert_no_tmp()

    def test_successful_export_is_private_and_json_complete(self):
        code, result = self.cli_export()
        self.assertEqual(code, 1)  # normal delivery is never authorized
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(self.target.read_text()), result)
        self.assertEqual(result['disposition'], 'NOT_ADMITTED')
        self.assert_no_tmp()

    def test_two_concurrent_writers_only_one_can_publish(self):
        def run(_):
            try:
                _write_receipt_create_only(str(self.target), '{"ok":true}\n')
                return 'CREATED'
            except FileExistsError:
                return 'EXISTS'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(run, (0, 1)))
        self.assertEqual(sorted(outcomes), ['CREATED', 'EXISTS'])
        self.assertEqual(json.loads(self.target.read_text()), {'ok': True})
        self.assert_no_tmp()

if __name__ == '__main__':
    unittest.main()
