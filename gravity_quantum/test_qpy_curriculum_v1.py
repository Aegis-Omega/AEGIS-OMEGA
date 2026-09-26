from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gravity_quantum.qpy_curriculum_v1 import (
    DEFAULT_TIME_SCALED,
    DET_TOLERANCE_SCALED,
    EXPECTED_QISKIT_VERSION,
    build_curriculum_receipt,
    build_curriculum_record,
    build_qiskit_circuit,
    emit_bundle,
    qiskit_statevector_point,
    qpy_roundtrip_bytes,
)


class ProofCarryingQpyCurriculumV1Test(unittest.TestCase):
    def test_qpy_roundtrip_is_deterministic_in_pinned_environment(self) -> None:
        circuit = build_qiskit_circuit(500_000)
        first, restored = qpy_roundtrip_bytes(circuit)
        second, _ = qpy_roundtrip_bytes(circuit)
        self.assertEqual(restored, circuit)
        self.assertEqual(first, second)
        self.assertGreater(len(first), 0)

    def test_t_zero_is_product_state(self) -> None:
        point = qiskit_statevector_point(0)
        self.assertTrue(point["pure_product_within_tolerance"])
        self.assertLessEqual(point["coeff_det_abs_scaled"], DET_TOLERANCE_SCALED)
        self.assertEqual(point["concurrence_scaled"], 0)

    def test_interaction_generates_entanglement_at_half_time(self) -> None:
        point = qiskit_statevector_point(500_000)
        self.assertFalse(point["pure_product_within_tolerance"])
        self.assertGreater(point["coeff_det_abs_scaled"], DET_TOLERANCE_SCALED)
        self.assertGreater(point["concurrence_scaled"], 0)

    def test_all_default_points_are_cross_framework_admissible(self) -> None:
        for time_scaled in DEFAULT_TIME_SCALED:
            with self.subTest(time_scaled=time_scaled):
                record = build_curriculum_record(time_scaled)
                self.assertTrue(record["checks"]["framework_agreement"])
                self.assertTrue(record["checks"]["qpy_roundtrip_equal"])
                self.assertTrue(record["checks"]["qiskit_version_pinned"])
                self.assertTrue(record["training"]["gradient_admissible"])
                self.assertEqual(record["training"]["training_weight_ppm"], 1_000_000)

    def test_formal_invariant_is_exact_head_bound(self) -> None:
        record = build_curriculum_record(0)
        formal = record["formal_invariant"]
        self.assertEqual(
            formal["theorem"],
            "coeffDet_eq_zero_iff_pureProductCoeffs",
        )
        self.assertEqual(len(formal["source_head"]), 40)
        self.assertEqual(len(formal["source_blob_sha"]), 40)

    def test_receipt_is_fail_closed_and_complete(self) -> None:
        receipt = build_curriculum_receipt()
        self.assertEqual(receipt["qiskit_version"], EXPECTED_QISKIT_VERSION)
        self.assertTrue(receipt["all_gradient_admissible"])
        self.assertEqual(receipt["record_count"], len(DEFAULT_TIME_SCALED))
        self.assertEqual(receipt["authority_effect"], "NONE")

    def test_emit_bundle_writes_qpy_jsonl_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = emit_bundle(root)
            self.assertTrue((root / "curriculum.jsonl").is_file())
            self.assertTrue((root / "receipt.json").is_file())
            self.assertEqual(
                len(list(root.glob("*.qpy"))),
                len(DEFAULT_TIME_SCALED),
            )
            self.assertEqual(
                len(receipt["qpy_artifacts"]),
                len(DEFAULT_TIME_SCALED),
            )


if __name__ == "__main__":
    unittest.main()
