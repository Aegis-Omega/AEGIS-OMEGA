from __future__ import annotations

from pathlib import Path
import unittest

from aegis_learning.quantumdna_adapter_v1 import (
    HOSTED_JOB_ID,
    HOSTED_RUN_ID,
    SOURCE_HEAD,
    compile_quantumdna_ledger,
    load_snapshot,
    validate_ledger_chain,
)

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "quantumdna_witness_ledger_v1.json"
)


class QuantumDnaAdapterV1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = load_snapshot(FIXTURE)

    def test_snapshot_chain_reconstructs(self) -> None:
        terminal = validate_ledger_chain(self.ledger)
        self.assertEqual(terminal, self.ledger["terminal_sha256"])

    def test_tri_stream_counts_are_exact(self) -> None:
        receipt = compile_quantumdna_ledger(self.ledger)
        self.assertEqual(receipt["record_count"], 16)
        self.assertEqual(receipt["counts"]["POSITIVE"], 3)
        self.assertEqual(receipt["counts"]["CONTRASTIVE_ONLY"], 10)
        self.assertEqual(receipt["counts"]["QUARANTINE"], 3)

    def test_verified_claim_becomes_scoped_positive(self) -> None:
        receipt = compile_quantumdna_ledger(self.ledger)
        record = next(r for r in receipt["records"] if r["claim_id"] == "CLM-452")
        self.assertEqual(record["learning"]["disposition"], "POSITIVE")
        self.assertEqual(
            record["target"]["desired_behavior"],
            "ACCEPT_WITH_DECLARED_SCOPE",
        )
        self.assertEqual(record["learning"]["positive_gradient_weight_ppm"], 1_000_000)

    def test_removed_claim_becomes_contrastive_pair(self) -> None:
        receipt = compile_quantumdna_ledger(self.ledger)
        record = next(r for r in receipt["records"] if r["claim_id"] == "CLM-455")
        self.assertEqual(
            record["learning"]["disposition"],
            "CONTRASTIVE_ONLY",
        )
        self.assertIn("0.21646991105146732", record["target"]["correction"])
        self.assertEqual(
            record["target"]["desired_behavior"],
            "REJECT_OR_CORRECT",
        )
        self.assertEqual(record["learning"]["positive_gradient_weight_ppm"], 0)
        self.assertEqual(record["learning"]["contrastive_weight_ppm"], 1_000_000)

    def test_proposed_claim_is_quarantined(self) -> None:
        receipt = compile_quantumdna_ledger(self.ledger)
        record = next(r for r in receipt["records"] if r["claim_id"] == "CLM-465")
        self.assertEqual(record["learning"]["disposition"], "QUARANTINE")
        self.assertEqual(
            record["target"]["desired_behavior"],
            "DEFER_PENDING_EVIDENCE",
        )
        self.assertEqual(record["learning"]["positive_gradient_weight_ppm"], 0)

    def test_hosted_replay_binding_is_exact(self) -> None:
        receipt = compile_quantumdna_ledger(self.ledger)
        hosted = receipt["hosted_attestation"]
        self.assertEqual(hosted["source_head"], SOURCE_HEAD)
        self.assertEqual(hosted["run_id"], HOSTED_RUN_ID)
        self.assertEqual(hosted["job_id"], HOSTED_JOB_ID)
        self.assertEqual(hosted["conclusion"], "success")
        self.assertIn(
            "Validate claims ledger",
            hosted["executed_steps"],
        )

    def test_authority_never_promoted(self) -> None:
        receipt = compile_quantumdna_ledger(self.ledger)
        self.assertEqual(receipt["authority_effect"], "NONE")
        self.assertTrue(
            all(r["authority_effect"] == "NONE" for r in receipt["records"])
        )

    def test_receipt_is_deterministic(self) -> None:
        a = compile_quantumdna_ledger(self.ledger)
        b = compile_quantumdna_ledger(self.ledger)
        self.assertEqual(a["receipt_sha256"], b["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
