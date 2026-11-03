"""Offline, source-bound checks for the shared agent setup preflight."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name('agent-env-setup.sh')


class SharedEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = pathlib.Path(self.t.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run_verify(self, *args):
        return subprocess.run(['bash', str(SCRIPT), '--verify', *(args or (str(self.repo),))],
                              capture_output=True, text=True, timeout=10)

    def test_empty_git_checkout(self):
        r = self.run_verify()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('AEGIS_AGENT_ENV=DEPENDENCIES_PRESENT', r.stdout)

    def test_nonrepo_refused(self):
        target = self.root / 'not-a-repo'
        target.mkdir()
        r = self.run_verify(str(target))
        self.assertEqual(r.returncode, 2)
        self.assertIn('AEGIS_AGENT_ENV=BLOCKED', r.stdout)

    def test_missing_checkout_refused(self):
        r = self.run_verify(str(self.root / 'missing'))
        self.assertEqual(r.returncode, 2)

    def test_missing_node_modules_refused(self):
        package = self.repo / 'hub'
        package.mkdir()
        (package / 'package.json').write_text('{}')
        r = self.run_verify()
        self.assertEqual(r.returncode, 2)
        self.assertIn('hub/node_modules', r.stdout)

    def test_present_node_modules_passes_presence_gate(self):
        if shutil.which('node') is None:
            self.skipTest('node runtime unavailable to test presence PASS')
        package = self.repo / 'hub'
        package.mkdir()
        (package / 'package.json').write_text('{}')
        (package / 'node_modules').mkdir()
        r = self.run_verify()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_required_python_import_refused(self):
        package = self.repo / 'packages/aegis-py'
        package.mkdir(parents=True)
        (package / 'pyproject.toml').write_text('[project]\nname="aegis-fixture"\n')
        # Running with system python that has no local fixture's aegis module
        # cannot be presumed guaranteed globally; use an intentionally minimal PATH
        # shell stub for python3. It returns failure only for import checks.
        fakebin = self.root / 'fakebin'
        fakebin.mkdir()
        p = fakebin / 'python3'
        p.write_text('#!/bin/sh\nexit 1\n')
        p.chmod(0o755)
        env = os.environ.copy()
        env['PATH'] = str(fakebin) + os.pathsep + os.environ.get('PATH', '')
        r = subprocess.run(['bash', str(SCRIPT), '--verify', str(self.repo)],
                           env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 2)
        self.assertIn('required aegis import unavailable', r.stdout)

    def test_unknown_options_rejected(self):
        r = subprocess.run(['bash', str(SCRIPT), '--destroy', str(self.repo)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 2)

    def test_no_writes_in_verify_mode(self):
        package = self.repo / 'hub'
        package.mkdir()
        (package / 'package.json').write_text('{}')
        before = sorted(str(p.relative_to(self.repo)) for p in self.repo.rglob('*'))
        self.run_verify()
        after = sorted(str(p.relative_to(self.repo)) for p in self.repo.rglob('*'))
        self.assertEqual(before, after)

    def test_worktree_git_file(self):
        subprocess.run(['git', '-C', str(self.repo), 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'config', 'user.name', 'Fixture'], check=True)
        (self.repo / 'README').write_text('test')
        subprocess.run(['git', '-C', str(self.repo), 'add', 'README'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-qm', 'fixture'], check=True)
        worktree = self.root / 'worktree'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', '-b', 'fixture-worktree', str(worktree)], check=True)
        self.assertTrue((worktree / '.git').is_file())
        r = self.run_verify(str(worktree))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_best_effort_is_not_verified(self):
        r = subprocess.run(['bash', str(SCRIPT), str(self.repo)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertIn('AEGIS_AGENT_ENV=BEST_EFFORT', r.stdout)
        self.assertNotIn('AEGIS_AGENT_ENV=DEPENDENCIES_PRESENT', r.stdout)


if __name__ == '__main__':
    unittest.main()
