#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from harness.sdk.dual_report import build_dual_report, verify_dual_report  # noqa: E402
from harness.sdk.sovereign_execution import ADMITTED, DENIED, SovereignExecutionError  # noqa: E402

COMMIT = "a" * 40


def authority_result(outcome: str = ADMITTED) -> dict:
    denial_codes = [] if outcome == ADMITTED else ["APPROVAL_MISSING"]
    return {
        "schema_version": "1.0.0",
        "outcome": outcome,
        "execution_identity_root": "1" * 64,
        "workspace_binding": "2" * 64,
        "workspace_decision_root": "3" * 64,
        "policy_decision": {
            "schema_version": "1.0.0",
            "outcome": outcome,
            "authority_score": "0.810000" if outcome == ADMITTED else "0.000000",
            "action_class": "D2",
            "authority_domain": "github:contents",
            "requested_capability": "repository.mutate",
            "tool": "git",
            "target_digest": "4" * 64,
            "identity_root": "1" * 64,
            "workspace_binding": "2" * 64,
            "registry_root": "7" * 64,
            "policy_root": "8" * 64,
            "denial_codes": denial_codes,
            "decision_root": "5" * 64,
        },
        "mutation_receipt_root": "6" * 64,
        "observation": {
            "actual_cwd": "/tmp/aegis",
            "access_token": "must-not-leak",
        },
    }


class DualReportContractTests(TestCase):
    def test_admitted_report_is_exact_head_bound_and_verifiable(self) -> None:
        document = build_dual_report(authority_result(), source_commit=COMMIT)
        self.assertEqual(document["source_commit_state"], "BOUND")
        self.assertEqual(document["source_commit"], COMMIT)
        self.assertEqual(document["reports"]["report_kind"], "AUTOMATON3_AUTHORITY_DECISION")
        self.assertIn(COMMIT, document["reports"]["human"]["markdown"])
        self.assertTrue(verify_dual_report(document))

    def test_machine_payload_is_deterministically_redacted(self) -> None:
        document = build_dual_report(authority_result(), source_commit=COMMIT)
        encoded = json.dumps(document, sort_keys=True)
        self.assertNotIn("must-not-leak", encoded)
        token = document["observation"]["access_token"]
        self.assertEqual(token["redacted"], True)
        self.assertRegex(token["sha256"], r"^[0-9a-f]{64}$")

    def test_tampered_machine_payload_is_rejected(self) -> None:
        document = build_dual_report(authority_result(), source_commit=COMMIT)
        tampered = copy.deepcopy(document)
        tampered["workspace_binding"] = "9" * 64
        with self.assertRaisesRegex(SovereignExecutionError, "MACHINE_PAYLOAD_HASH_MISMATCH"):
            verify_dual_report(tampered)

    def test_tampered_human_rendering_is_rejected(self) -> None:
        document = build_dual_report(authority_result(), source_commit=COMMIT)
        tampered = copy.deepcopy(document)
        tampered["reports"]["human"]["markdown"] += "tampered\n"
        with self.assertRaisesRegex(SovereignExecutionError, "HUMAN_RENDERING_MISMATCH"):
            verify_dual_report(tampered)

    def test_admitted_report_without_exact_head_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            SovereignExecutionError, "ADMITTED_REPORT_REQUIRES_EXACT_SOURCE_COMMIT"
        ):
            build_dual_report(authority_result(), source_commit=None)

    def test_denied_report_can_state_exact_head_unavailable(self) -> None:
        document = build_dual_report(
            {"schema_version": "1.0.0", "outcome": DENIED, "denial_codes": ["IDENTITY_INVALID"]},
            source_commit=None,
        )
        self.assertEqual(document["source_commit_state"], "UNAVAILABLE")
        self.assertIn("IDENTITY_INVALID", document["reports"]["human"]["markdown"])
        self.assertTrue(verify_dual_report(document))

    def test_reserved_reports_field_cannot_be_preinjected(self) -> None:
        payload = authority_result()
        payload["reports"] = {"forged": True}
        with self.assertRaisesRegex(SovereignExecutionError, "REPORTS_FIELD_RESERVED"):
            build_dual_report(payload, source_commit=COMMIT)

    def test_cli_denial_emits_machine_and_human_views(self) -> None:
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "automaton3-authority.py"), "evaluate", "--human-output", "-"],
            input="{}",
            text=True,
            capture_output=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(process.returncode, 3)
        document = json.loads(process.stdout)
        self.assertEqual(process.stderr, document["reports"]["human"]["markdown"])
        self.assertTrue(verify_dual_report(document))


if __name__ == "__main__":
    main()
