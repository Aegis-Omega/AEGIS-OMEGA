import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('ledger', Path(__file__).resolve().parents[1] / 'integration_ledger.py')
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.git('init')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        Path('module').mkdir()
        Path('module/code.py').write_text('pass\n')
        self.commit()
    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()
    def git(self, *args):
        return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout.strip()
    def commit(self):
        self.git('add', '.')
        self.git('commit', '-m', 'fixture')
        return self.git('rev-parse', 'HEAD')
    def test_untracked_configuration_does_not_change_snapshot(self):
        before = ledger.build_rows()
        Path('module/vercel.json').write_text('{}')
        self.assertEqual(before, ledger.build_rows())
    def test_comment_cannot_claim_execution(self):
        Path('.github/workflows').mkdir(parents=True)
        Path('.github/workflows/test.yml').write_text('# module/ is disabled\n')
        self.commit()
        self.assertNotEqual(ledger.build_rows()[0][0], 'WIRED')
    def test_committed_configuration_is_only_linked(self):
        Path('module/vercel.json').write_text('{}')
        self.commit()
        self.assertEqual(ledger.build_rows()[0][0], 'LINKED')
    def test_old_commit_stable_after_new_commit(self):
        sha = self.git('rev-parse', 'HEAD')
        before = ledger.committed_rows(sha)
        Path('module/vercel.json').write_text('{}')
        self.commit()
        self.assertEqual(before, ledger.committed_rows(sha))
    def test_invalid_commit_rejected(self):
        with self.assertRaises(subprocess.CalledProcessError):
            ledger.committed_rows('0' * 40)
    def test_dirty_tracked_file_does_not_change_snapshot(self):
        Path('ref.py').write_text('pass\n')
        self.commit()
        before = ledger.build_rows()
        Path('ref.py').write_text('# module/\n')
        self.assertEqual(before, ledger.build_rows())

    def test_subdirectory_execution_scans_the_entire_commit(self):
        sha = self.git('rev-parse', 'HEAD')
        before = ledger.committed_rows(sha)
        os.chdir('module')
        self.assertEqual(before, ledger.committed_rows(sha))

    def test_replacement_commit_cannot_change_bound_snapshot(self):
        sha = self.git('rev-parse', 'HEAD')
        before_rows = ledger.committed_rows(sha)
        before_meta = ledger.metadata()
        Path('module/vercel.json').write_text('{}')
        replacement = self.commit()
        self.git('checkout', '--detach', sha)
        self.git('replace', sha, replacement)
        self.assertEqual(before_rows, ledger.committed_rows(sha))
        self.assertEqual(before_meta, ledger.metadata())

    def test_symbolic_reference_is_not_an_exact_commit(self):
        with self.assertRaises(ValueError):
            ledger.committed_rows('HEAD')

    def test_abbreviated_sha_is_not_an_exact_commit(self):
        sha = self.git('rev-parse', 'HEAD')
        with self.assertRaises(ValueError):
            ledger.committed_rows(sha[:12])

    def test_tree_oid_is_not_a_commit(self):
        tree = self.git('rev-parse', 'HEAD^{tree}')
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            ledger.committed_rows(tree)

    def test_committed_external_files_drive_reference_thresholds(self):
        Path('module/code.py').write_text('# module/ self-reference\n' * 4)
        Path('runner1.py').write_text('# module/ repeated in one file\n' * 4)
        self.commit()
        row = next(row for row in ledger.build_rows() if row[1] == 'module')
        self.assertEqual(row[0], 'DORMANT')
        self.assertIn('1 committed lexical references', row[2])

        Path('runner2.py').write_text('# module/\n')
        self.commit()
        row = next(row for row in ledger.build_rows() if row[1] == 'module')
        self.assertEqual(row[0], 'DORMANT')
        self.assertIn('2 committed lexical references', row[2])

        Path('.github/workflows').mkdir(parents=True)
        Path('.github/workflows/test.yml').write_text(
            'jobs:\n  test:\n    steps:\n      - run: python module/code.py\n'
        )
        self.commit()
        row = next(row for row in ledger.build_rows() if row[1] == 'module')
        self.assertEqual(row[0], 'LINKED')
        self.assertIn('3 committed lexical references', row[2])
        self.assertNotIn('WIRED', [row[0] for row in ledger.build_rows()])

    def test_excluded_blobs_cannot_supply_references_or_configuration(self):
        for name in (
            'README.md',
            'notes.MD',
            'node_modules/vendor/ref.py',
            'tools/node_modules/vendor/ref.py',
            'tools/target/ref.py',
            'tools/build/ref.py',
        ):
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('module/\n')
        Path('binary.dat').write_bytes(b'\0module/\n')
        Path('shortcut').symlink_to('module/code.py')
        Path('configuration.json').write_text('{}')
        Path('module/vercel.json').symlink_to('../configuration.json')
        self.commit()
        row = next(row for row in ledger.build_rows() if row[1] == 'module')
        self.assertEqual(row[0], 'ORPHAN')
        self.assertNotIn('configuration', row[2])

if __name__ == '__main__':
    unittest.main()
