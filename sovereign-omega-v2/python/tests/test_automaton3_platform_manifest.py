#!/usr/bin/env python3
"""Automaton-3 replay evidence must carry the live platform effect boundary."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / "scripts" / "validate-automaton3.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_automaton3", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Automaton3PlatformManifestTests(unittest.TestCase):
    def test_replay_manifest_contains_every_live_platform_effect_transition_artifact(self) -> None:
        validator = load_validator()
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            summary = tmp / "summary.json"
            log = tmp / "mcp.log"
            summary.write_text(json.dumps({
                "return_code": 0,
                "bypasses": 0,
                "adaptive_attempts": [1, 10, 100],
                "expected_test_count": 41,
                "operator_visibility_asserted": True,
                "state_preservation_asserted": True,
                "external_side_effect_absence_asserted": True,
                "summary_root": "1" * 64,
            }), encoding="utf-8")
            log.write_text("AUTOMATON3_MCP_PASS\n", encoding="utf-8")
            receipt, manifest = validator.evaluate(
                candidate_sha="a" * 40,
                expected_parent_sha="b" * 40,
                test_summary_path=summary,
                mcp_log_path=log,
                require_oidc=False,
            )

            with patch.dict("os.environ", {
                "GITHUB_ACTIONS": "true",
                "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example.invalid",
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "test-token",
            }, clear=True):
                hosted_receipt, _ = validator.evaluate(
                    candidate_sha="a" * 40,
                    expected_parent_sha="b" * 40,
                    test_summary_path=summary,
                    mcp_log_path=log,
                    require_oidc=True,
                )

            with patch.dict("os.environ", {}, clear=True):
                missing_oidc_receipt, _ = validator.evaluate(
                    candidate_sha="a" * 40,
                    expected_parent_sha="b" * 40,
                    test_summary_path=summary,
                    mcp_log_path=log,
                    require_oidc=True,
                )

        self.assertEqual("ADMITTED", receipt["outcome"], receipt["violations"])
        self.assertEqual("UNSIGNED_LOCAL", receipt["signature_mode"])
        self.assertEqual("ADMITTED", hosted_receipt["outcome"], hosted_receipt["violations"])
        self.assertEqual("GITHUB_OIDC_PENDING_ATTESTATION", hosted_receipt["signature_mode"])
        self.assertEqual("DENIED", missing_oidc_receipt["outcome"])
        self.assertEqual("UNSIGNED_LOCAL", missing_oidc_receipt["signature_mode"])
        self.assertIn("OIDC execution identity unavailable", missing_oidc_receipt["violations"])
        paths = {record["path"] for record in manifest["files"]}
        required = {
            "harness/sdk/transition_receipts.py",
            "harness/sdk/effect_adapters.py",
            "harness/sdk/effect_verifier.py",
            "harness/sdk/complete_verifier.py",
            "harness/sdk/platform_effect_adapter.py",
            "harness/sdk/proof_carrying_platform_execution.py",
            "scripts/automaton3-platform-execute.py",
            "scripts/agent_dispatch_payload.py",
            "scripts/test_agent_dispatch_payload.py",
            "sovereign-omega-v2/python/bridge.py",
            "sovereign-omega-v2/python/platform_helpers.py",
            "sovereign-omega-v2/python/tests/test_bridge_execution_id_binding.py",
            "sovereign-omega-v2/python/tests/test_platform_effect_chain_live.py",
            "sovereign-omega-v2/python/tests/test_automaton3_platform_manifest.py",
            ".github/workflows/agent-dispatch.yml",
            ".github/workflows/authorization-effect-chain.yml",
        }
        self.assertEqual(set(), required - paths)


if __name__ == "__main__":
    unittest.main()
