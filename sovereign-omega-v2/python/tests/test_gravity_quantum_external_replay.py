from __future__ import annotations

import unittest

from gravity_quantum_external_replay import (
    kernel_receipt_from_external,
    verify_external_replay,
)

OLD_HEAD = "04ae6f39ad6d7c32396926034afdd111ccc95daf"
CURRENT_HEAD = "dba46e59519e56670989dacc07294c7fbea3ff4c"
SOURCE = "dc4be9af134b99346a8fc3b0a29bfb274328a2d202167b69fedde4928c839b00"


def status_fixture(*, head=CURRENT_HEAD, verified=True, stage="VERIFIED_EXACT_SOURCE"):
    return {
        "receipt_kind": "AEGIS_GQ_CLOUDFLARE_LEAN_REPLAY_V1",
        "head_sha": head,
        "source_sha256": SOURCE,
        "lean_target": "4.33.1",
        "mathlib_sha": "0df444a360eaa60ab8c11dca51a86af692955474",
        "target_module": "GravityQuantumPureProductV1",
        "stage": stage,
        "verified": verified,
        "authority_effect": "NONE",
        "gravity_quantized": False,
        "quantum_gravity_proven": False,
    }


class ExternalReplayTests(unittest.TestCase):
    def test_stale_external_receipt_denies(self):
        result = verify_external_replay(
            status_fixture(head=OLD_HEAD, verified=False, stage="LEAN_COMPILE_FAILED"),
            expected_head=CURRENT_HEAD,
            expected_source_sha256=SOURCE,
        )
        self.assertEqual(result["decision"], "DENY")
        self.assertIn("STALE_OR_WRONG_HEAD", result["reason_codes"])

    def test_matching_head_but_failed_replay_denies(self):
        result = verify_external_replay(
            status_fixture(verified=False, stage="LEAN_COMPILE_FAILED"),
            expected_head=CURRENT_HEAD,
            expected_source_sha256=SOURCE,
        )
        self.assertEqual(result["decision"], "DENY")
        self.assertIn("REPLAY_NOT_VERIFIED", result["reason_codes"])
        self.assertIn("REPLAY_STAGE_NOT_VERIFIED", result["reason_codes"])

    def test_matching_verified_receipt_can_mint_bounded_kernel_receipt(self):
        status = status_fixture()
        result = verify_external_replay(
            status,
            expected_head=CURRENT_HEAD,
            expected_source_sha256=SOURCE,
        )
        self.assertEqual(result["decision"], "PASS")
        kernel = kernel_receipt_from_external(
            status,
            expected_head=CURRENT_HEAD,
            expected_source_sha256=SOURCE,
        )
        self.assertEqual(kernel["kernel_replay"], "PASS")
        self.assertEqual(kernel["axiom_audit"], "PASS")
        self.assertFalse(kernel["sorryAx_present"])
        self.assertEqual(kernel["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
