"""Pure-stdlib, offline regression and falsification tests for Circle/Codex binding."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('circle_mcp_preflight.py')
spec = importlib.util.spec_from_file_location('circle_preflight', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CirclePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'private-codex-home'
        self.home.mkdir()

    def write(self, data):
        (self.home / 'config.toml').write_text(data, encoding='utf-8')

    def test_no_config(self):
        self.assertEqual(m.inspect_config(self.home)['status'], 'NOT_CONFIGURED')

    def test_existing_unrelated_entry(self):
        self.write('[mcp_servers.other]\nurl="https://example.test/mcp"\n')
        self.assertEqual(m.inspect_config(self.home)['status'], 'NOT_CONFIGURED')

    def test_registered_does_not_mean_connected(self):
        self.write('[mcp_servers.circle]\nurl="'+m.CIRCLE_URL+'"\n')
        info = m.inspect(self.home, None)
        self.assertEqual(info['config']['status'], 'CONFIGURED_ONLY')
        self.assertEqual(info['live_transport'], 'NOT_TESTED')
        self.assertEqual(info['auth'], 'NOT_TESTED')
        self.assertFalse(info['authority_granted'])

    def test_wrong_url(self):
        self.write('[mcp_servers.circle]\nurl="https://malicious.invalid/mcp"\n')
        self.assertEqual(m.inspect_config(self.home)['status'], 'MISMATCH_OR_UNSUPPORTED')

    def test_disabled(self):
        self.write('[mcp_servers.circle]\nurl="'+m.CIRCLE_URL+'"\nenabled=false\n')
        self.assertEqual(m.inspect_config(self.home)['status'], 'DISABLED')

    def test_invalid_toml(self):
        self.write('[mcp_servers.circle\n')
        self.assertEqual(m.inspect_config(self.home)['status'], 'UNREADABLE_CONFIG')

    def test_symlink_rejected(self):
        other = Path(self.temp.name) / 'target'
        other.write_text('[mcp_servers.circle]\nurl="'+m.CIRCLE_URL+'"')
        (self.home / 'config.toml').symlink_to(other)
        self.assertEqual(m.inspect_config(self.home)['status'], 'UNSAFE_CONFIG_PATH')
        self.assertEqual(m.register(self.home, '/does-not-exist'), 'DENIED_UNSAFE_PATH')
        self.assertIn('mcp_servers.circle', other.read_text())

    def test_registration_never_overwrites_different_url(self):
        original = '[mcp_servers.circle]\nurl="https://another.example/"\n'
        self.write(original)
        self.assertEqual(m.register(self.home, '/does-not-exist'), 'DENIED_EXISTING_CONFIG')
        self.assertEqual((self.home/'config.toml').read_text(), original)

    def test_registration_no_cli_is_denied(self):
        self.assertEqual(m.register(self.home, None), 'NO_VERIFIED_CODEX')
        self.assertFalse((self.home/'config.toml').exists())

    def test_cli_failure_not_pass(self):
        with patch.object(m.subprocess, 'run') as call:
            call.return_value.returncode = 1
            call.return_value.stdout = 'codex 9.9'
            self.assertEqual(m.cli_version('codex')['status'], 'UNVERIFIED')

    def test_official_codex_cli_version_prefix(self):
        with patch.object(m.subprocess, 'run') as call:
            call.return_value.returncode = 0
            call.return_value.stdout = 'codex-cli 0.158.0\n'
            self.assertEqual(m.cli_version('codex')['status'], 'VERSION_CONFIRMED')

    def test_cli_wrong_output_not_pass(self):
        with patch.object(m.subprocess, 'run') as call:
            call.return_value.returncode = 0
            call.return_value.stdout = 'not-codex 1.0'
            self.assertEqual(m.cli_version('fake')['status'], 'UNVERIFIED')

    def test_valid_explicit_registration(self):
        def fake_run(argv, **kwargs):
            class Result: pass
            ret = Result()
            ret.returncode = 0
            ret.stdout = 'codex 0.100.0' if argv[1:] == ['--version'] else ''
            if argv[1:4] == ['mcp', 'add', 'circle']:
                self.assertEqual(kwargs['env']['CODEX_HOME'], str(self.home))
                self.assertIn(m.CIRCLE_URL, argv)
                self.write('[mcp_servers.circle]\nurl="'+m.CIRCLE_URL+'"\n')
            return ret
        with patch.object(m.subprocess, 'run', side_effect=fake_run):
            self.assertEqual(m.register(self.home, '/fake/codex'), 'REGISTERED_CONFIG_ONLY')
            self.assertEqual(m.inspect_config(self.home)['status'], 'CONFIGURED_ONLY')

    def test_no_false_success_when_cli_claims_ok_without_config(self):
        with patch.object(m.subprocess, 'run') as call:
            call.return_value.returncode = 0
            call.return_value.stdout = 'codex 0.100.0'
            self.assertEqual(m.register(self.home, '/fake/codex'), 'REGISTRATION_NOT_VERIFIED')

    def test_main_with_no_binary_exit_nonzero(self):
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), patch.object(m.shutil, 'which', return_value=None):
            status = m.main(['--codex-home', str(self.home)])
        report = json.loads(sink.getvalue())
        self.assertEqual(status, 1)
        self.assertEqual(report['config']['status'], 'NOT_CONFIGURED')
        self.assertEqual(report['live_transport'], 'NOT_TESTED')


if __name__ == '__main__':
    unittest.main()
