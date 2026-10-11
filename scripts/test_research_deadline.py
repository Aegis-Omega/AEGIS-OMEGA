"""Actual OS-subprocess deadline and fail-closed collector CLI supervision."""
from __future__ import annotations
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import research_collector as rc
from test_research_collector import capture


class DeadlineTests(unittest.TestCase):
    def test_01_baseline_slow_body_defeats_per_io_timeout(self):
        # Simulated body drip: 5 x 30ms all < 8-second socket timeout.
        # Standalone acquire has no end-to-end time budget: don't claim it does.
        class Drip:
            status=200
            chunked=False
            def getheader(self,name):
                return {'Content-Type':'text/plain','Content-Length':'5'}.get(name)
            def read(self,limit):
                for _ in range(5):time.sleep(.03)
                return b'Hello'
        class Sock:
            def getpeercert(self, binary_form=False):return b'test-only-cert'
        class FakeConn:
            sock=Sock()
            def __init__(self,*a,**kw): pass
            def connect(self): pass
            def request(self,*a,**kw): pass
            def getresponse(self):return Drip()
            def close(self):pass
        from test_research_collector import res
        started=time.monotonic()
        result=rc.acquire('https://docs.example.org/x',('docs.example.org',),
                          connection_factory=FakeConn,resolver=lambda *a,**k:res())
        self.assertEqual(result['full_bytes'],5)
        self.assertGreater(time.monotonic()-started,.11)

    def test_02_subprocess_slow_worker_killed_before_completion(self):
        code='import time; time.sleep(5);print(\'{"ok":true}\')'
        start=time.monotonic()
        with self.assertRaisesRegex(rc.CaptureDenied, 'TOTAL_DEADLINE_EXCEEDED'):
            rc._run_bounded_worker([sys.executable,'-c',code],deadline_seconds=1)
        self.assertLess(time.monotonic()-start,3.5)

    def test_03_subprocess_partial_output_then_drip_killed(self):
        code="import sys,time;sys.stdout.write(\"{\");sys.stdout.flush();time.sleep(5)"
        with self.assertRaisesRegex(rc.CaptureDenied,'TOTAL_DEADLINE_EXCEEDED'):
            rc._run_bounded_worker([sys.executable,'-c',code],deadline_seconds=1)

    def test_04_bounded_worker_success_json(self):
        code='import json;print(json.dumps({"complete":True}))'
        r=rc._run_bounded_worker([sys.executable,'-c',code],deadline_seconds=2)
        self.assertIs(r['complete'],True)

    def test_05_worker_nonzero_is_denied_and_no_stdout_trusted(self):
        code='import sys;print(\'{"schema":"forged"}\');sys.exit(4)'
        with self.assertRaisesRegex(rc.CaptureDenied,'WORKER_DENIED'):
            rc._run_bounded_worker([sys.executable,'-c',code],deadline_seconds=2)

    def test_06_worker_stdout_not_json_denied(self):
        with self.assertRaisesRegex(rc.CaptureDenied,'WORKER_RESULT_INVALID'):
            rc._run_bounded_worker([sys.executable,'-c','print("not-json")'], deadline_seconds=2)

    def test_07_invalid_budget_denied(self):
        for x in (0,-1,121,True,2.2,None):
            with self.subTest(x=x),self.assertRaisesRegex(rc.CaptureDenied,'INVALID_TOTAL_DEADLINE'):
                rc._deadline_value(x)

    def test_08_cli_rejects_invalid_host_before_starting_child(self):
        with patch.object(rc,'_run_bounded_worker',side_effect=AssertionError('child invoked')):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    rc.main(['https://evil.example.org/','--allow-host','docs.example.org',
                             '--allow-network','--deadline-seconds','2'])
        self.assertEqual(caught.exception.code,2)

    def test_09_timeout_creates_no_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'capture.json'
            def deadline(_command,*,deadline_seconds):
                raise rc.CaptureDenied('TOTAL_DEADLINE_EXCEEDED')
            with patch.object(rc,'_run_bounded_worker',side_effect=deadline):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        rc.main(['https://docs.example.org/page','--allow-host','docs.example.org',
                                 '--allow-network','--deadline-seconds','1',
                                 '--output',str(path)])
            self.assertEqual(caught.exception.code,2)
            self.assertFalse(path.exists())

    def test_10_success_parent_publishes_only_validated_capture(self):
        result=capture()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'capture.json'
            with patch.object(rc,'_run_bounded_worker',return_value=result):
                rc.main(['https://docs.example.org/page','--allow-host','docs.example.org',
                         '--allow-network','--deadline-seconds','2', '--output',str(path)])
            self.assertEqual(json.loads(path.read_text())['full_body_sha256'],result['full_body_sha256'])

    def test_11_parent_rejects_wrong_worker_source(self):
        result=capture();result['url']='https://elsewhere.example.org/page'
        with patch.object(rc,'_run_bounded_worker',return_value=result):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    rc.main(['https://docs.example.org/page','--allow-host','docs.example.org',
                             '--allow-network'])
        self.assertEqual(caught.exception.code,2)

    def test_12_worker_invoked_without_env_pythonpath_injection(self):
        code='import os,json;print(json.dumps({"pythonpath":os.getenv("PYTHONPATH"),"ssl":os.getenv("SSL_CERT_FILE")}))'
        with patch.dict(os.environ,{'PYTHONPATH':'/untrusted','SSL_CERT_FILE':'/untrusted/CA'}):
            result=rc._run_bounded_worker([sys.executable,'-c',code],deadline_seconds=2)
        self.assertIsNone(result['pythonpath'])
        self.assertIsNone(result['ssl'])

    def test_13_bootstrap_runs_isolated_without_web(self):
        script=str(Path(rc.__file__).resolve())
        argv=[sys.executable,'-I','-c',rc._WORKER_BOOTSTRAP,script,
              json.dumps({'url':'https://docs.example.org/page',
                          'hosts':['evil.example.org'],'key_file':None,
                          'key_id':None,'binding':None})]
        with self.assertRaisesRegex(rc.CaptureDenied,'WORKER_DENIED'):
            rc._run_bounded_worker(argv,deadline_seconds=3)


    def test_14_no_unbudgeted_cli_worker_mode(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                rc.main(['https://docs.example.org/page','--allow-host','docs.example.org',
                         '--_capture-worker'])
        self.assertEqual(caught.exception.code,2)

    def test_15_secret_file_path_not_secret_bytes_sent_to_worker(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'runner.key'
            secret=bytes(range(32))
            path.write_bytes(secret); path.chmod(0o600)
            result=capture()
            # Mock a signed result because this test inspects only the argv
            # boundary; cryptographic verification lives in other suites.
            result['attestation']={'synthetic':True}
            record=[]
            def fake_worker(argv,*,deadline_seconds):
                record.extend(argv)
                return result
            with patch.object(rc,'_run_bounded_worker',side_effect=fake_worker):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        rc.main(['https://docs.example.org/page','--allow-host','docs.example.org',
                                 '--allow-network','--deadline-seconds','2',
                                 '--signing-key-file',str(path),
                                 '--signing-key-id','synthetic.test',
                                 '--task-id','demo','--repo-head','a'*40,
                                 '--source-id','sample'])
            self.assertTrue(record)
            self.assertNotIn(secret.hex(),str(record))
            self.assertEqual(record[1:3],['-I','-c'])

    def test_16_malformed_worker_response_not_written(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/'capture.json'
            with patch.object(rc,'_run_bounded_worker',return_value={'spoof':True}):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        rc.main(['https://docs.example.org/page','--allow-host','docs.example.org',
                                 '--allow-network','--output',str(output)])
            self.assertEqual(caught.exception.code,2)
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
