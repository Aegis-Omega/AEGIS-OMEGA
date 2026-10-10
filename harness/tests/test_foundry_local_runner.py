"""Falsifiers and actual subprocess replay for the bounded AEGIS System Foundry.

No paid inference, network, accounts, or production deployments are required.
The local runner is not a hostile-code sandbox and is never an authority grant.
"""
from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.sdk.generator.foundry_runner import (
    LocalBuildError, _verify_artifacts, materialize_candidate, run_local_contract,
)
from harness.sdk.generator.system_foundry import (
    SystemBlueprintError, build_readonly_json_api,
)


def blueprint() -> dict:
    return {
        "system_id": "test-system", "kind": "readonly-json-api",
        "routes": {"/health": {"status": "ok"}, "/v1/events": {"n": 2}},
    }


class SystemFoundryLocalRunnerTests(unittest.TestCase):
    def test_real_generated_unittest_process(self):
        result = run_local_contract(blueprint())
        self.assertEqual(result["outcome"], "LOCAL_TEST_PASS")
        self.assertEqual(result["exit_code"], 0)
        self.assertGreaterEqual(result["test_count"], 3)
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["admission"], "NOT_ADMITTED")
        self.assertIs(result["authority_granted"], False)
        self.assertEqual(result["runner"], "LOCAL_PROCESS_NOT_A_SECURITY_SANDBOX")
        self.assertEqual(result["independent_oracle"]["outcome"], "ORACLE_PASS")
        self.assertEqual(result["independent_oracle"]["test_count"], 8)
        self.assertEqual(result["independent_oracle"]["passed_count"], 8)
        expected = {a.path: a.hash for a in build_readonly_json_api(blueprint())}
        self.assertEqual(result["artifacts"], expected)

    def test_execution_failure_not_promoted(self):
        # Compile a trusted template, then explicitly simulate a broken TEST
        # in a local fixture; the runner must not report a fake PASS.
        with patch(
            "harness.sdk.generator.system_foundry._TEST",
            'raise RuntimeError("BROKEN_CONTRACT_TEST")\n'
        ):
            result = run_local_contract(blueprint())
        self.assertEqual(result["outcome"], "LOCAL_TEST_FAIL")
        self.assertNotEqual(result["exit_code"], 0)
        self.assertEqual(result["test_count"], 0)
        self.assertEqual(result["admission"], "NOT_ADMITTED")

    def test_inert_hostile_payload(self):
        bad = blueprint()
        bad["routes"]["/health"] = {
            "text": "__import__('os').system('touch /tmp/dont_execute_me')"
        }
        result = run_local_contract(bad)
        self.assertEqual(result["outcome"], "LOCAL_TEST_PASS")
        self.assertEqual(result["test_count"], 3)

    def test_materialization_writes_exact_candidate_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "candidate"
            artifacts = materialize_candidate(blueprint(), dest)
            self.assertEqual(set(p.name for p in dest.iterdir()), {
                "service.py", "test_service.py", "README.md",
            })
            for item in artifacts:
                self.assertEqual(
                    hashlib.sha256((dest / item.path).read_bytes()).hexdigest(),
                    item.hash,
                )
            with self.assertRaisesRegex(LocalBuildError, "MUST_NOT_EXIST"):
                materialize_candidate(blueprint(), dest)

    def test_artifact_tamper_rejected(self):
        items = build_readonly_json_api(blueprint())
        items[0].content += "\n# altered"
        with self.assertRaisesRegex(LocalBuildError, "HASH_MISMATCH"):
            _verify_artifacts(items)

    def test_invalid_timeout_and_blueprint_rejected(self):
        for timeout in (0, -1, 31, True, "ten"):
            with self.subTest(timeout=timeout), self.assertRaises(LocalBuildError):
                run_local_contract(blueprint(), timeout_seconds=timeout)
        bad = blueprint()
        bad["routes"]["/"] = {"x": float("nan")}
        with self.assertRaises(SystemBlueprintError):
            run_local_contract(bad)

    def test_receipt_is_content_bound(self):
        a = run_local_contract(blueprint())
        b = blueprint()
        b["routes"]["/health"]["status"] = "changed"
        c = run_local_contract(b)
        self.assertNotEqual(a["blueprint_sha256"], c["blueprint_sha256"])
        self.assertNotEqual(a["receipt_sha256"], c["receipt_sha256"])
        self.assertNotEqual(a["artifacts"]["service.py"], c["artifacts"]["service.py"])

    def test_time_telemetry_does_not_mutate_deterministic_receipt(self):
        from types import SimpleNamespace
        import subprocess
        real_run = subprocess.run
        def stub(elapsed):
            fake = SimpleNamespace(
                returncode=0, stdout="",
                stderr="...\nRan 3 tests in " + elapsed + "s\n\nOK\n",
            )
            def proxy(args, *positional, **kw):
                if args[-1] == "test_service.py":
                    return fake
                return real_run(args, *positional, **kw)
            return proxy
        with patch("harness.sdk.generator.foundry_runner.subprocess.run", side_effect=stub("0.001")):
            left = run_local_contract(blueprint())
        with patch("harness.sdk.generator.foundry_runner.subprocess.run", side_effect=stub("0.983")):
            right = run_local_contract(blueprint())
        self.assertEqual(left["outcome"], "LOCAL_TEST_PASS")
        self.assertEqual(right["outcome"], "LOCAL_TEST_PASS")
        self.assertEqual(left["receipt_sha256"], right["receipt_sha256"])
        self.assertNotEqual(
            left["unattested_observation"]["stderr_raw_sha256"],
            right["unattested_observation"]["stderr_raw_sha256"],
        )

    def test_fake_self_test_ok_cannot_hide_broken_service(self):
        from harness.sdk.generator import system_foundry
        broken = system_foundry._SOURCE.replace(
            'status, payload = "200 OK", ROUTES[path]',
            'status, payload = "200 OK", {"hijacked": True}',
        )
        self.assertNotEqual(broken, system_foundry._SOURCE)
        forged_test = "import sys\nsys.stderr.write(" + repr("Ran 3 tests in 0.001s\n\nOK\n") + ")\n"
        with patch("harness.sdk.generator.system_foundry._SOURCE", broken):
            with patch("harness.sdk.generator.system_foundry._TEST", forged_test):
                result = run_local_contract(blueprint())
        self.assertEqual(result["outcome"], "LOCAL_TEST_FAIL")
        self.assertEqual(result["independent_oracle"]["outcome"], "ORACLE_FAIL")
        self.assertLess(
            result["independent_oracle"]["passed_count"],
            result["independent_oracle"]["test_count"],
        )
        self.assertEqual(result["admission"], "NOT_ADMITTED")

    def test_empty_environment_does_not_leak_secret_into_receipt(self):
        with patch.dict("os.environ", {"AEGIS_SENSITIVE_TEST_SECRET": "DONT_LEAK"}, clear=False):
            result = run_local_contract(blueprint())
        self.assertNotIn("DONT_LEAK", json.dumps(result))
        self.assertIs(result["authority_granted"], False)


if __name__ == "__main__":
    unittest.main()
