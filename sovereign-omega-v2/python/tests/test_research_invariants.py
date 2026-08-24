import hashlib
import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import research_invariants as ri


class ZeroDiscretionTypeGateTests(unittest.TestCase):
    def test_type_registry_is_zero_discretion_and_fail_closed(self):
        self.assertEqual(
            ri.required_gates_for_type("DiscretizedSpectralBasisV1"),
            ("spectral-domain-coverage",),
        )
        with self.assertRaises(KeyError):
            ri.required_gates_for_type("MadeUpSpectralThing")

    def test_spectral_basis_blocks_underresolved_domain(self):
        # 12*pi/3.5 = 10.771... < 14.13: canonical evening regression.
        with self.assertRaises(ri.InvariantViolationError) as ctx:
            ri.SpectralBasis(n_f=12, h=3.5, target_gamma_max=14.13)
        receipt = ctx.exception.receipt
        self.assertEqual(receipt.gate_id, "spectral-domain-coverage")
        self.assertEqual(receipt.verdict, ri.GateVerdict.FAIL)
        self.assertLess(receipt.observation["cutoff"], 14.13)

    def test_spectral_basis_passes_when_cutoff_covers_target(self):
        basis = ri.SpectralBasis(n_f=16, h=3.5, target_gamma_max=14.13)
        self.assertGreaterEqual(basis.nyquist_cutoff, 14.13)
        self.assertEqual(basis.gate_receipts[0].verdict, ri.GateVerdict.PASS)

    def test_operator_decomposition_conservation(self):
        operator = [[2.0, 1.0], [1.0, 2.0]]
        parts = [
            [[1.0, 1.0], [0.0, 1.0]],
            [[1.0, 0.0], [1.0, 1.0]],
        ]
        receipt = ri.operator_decomposition_gate(operator, parts, tolerance=0.0)
        self.assertEqual(receipt.verdict, ri.GateVerdict.PASS)
        self.assertEqual(receipt.observation["residual_fro"], 0.0)

    def test_operator_decomposition_detects_missing_term(self):
        operator = [[2.0, 1.0], [1.0, 2.0]]
        parts = [[[1.0, 1.0], [0.0, 1.0]]]
        receipt = ri.operator_decomposition_gate(operator, parts, tolerance=0.0)
        self.assertEqual(receipt.verdict, ri.GateVerdict.FAIL)
        self.assertGreater(receipt.observation["residual_fro"], 0.0)

    def test_skew_symmetric_quadratic_identity(self):
        matrix = [[0.0, 2.0], [-2.0, 0.0]]
        receipt = ri.skew_quadratic_gate(
            matrix,
            witness_vectors=[[1.0, 3.0], [-4.0, 7.0]],
            tolerance=0.0,
        )
        self.assertEqual(receipt.verdict, ri.GateVerdict.PASS)
        self.assertEqual(receipt.observation["skew_residual_fro"], 0.0)
        self.assertEqual(receipt.observation["max_abs_xTAx"], 0.0)

    def test_laplacian_kernel_one(self):
        laplacian = [[1.0, -1.0], [-1.0, 1.0]]
        receipt = ri.laplacian_kernel_gate(laplacian, tolerance=0.0)
        self.assertEqual(receipt.verdict, ri.GateVerdict.PASS)
        self.assertEqual(receipt.observation["residual_inf"], 0.0)

    def test_dual_certificate(self):
        a_matrix = [[1.0, 0.0], [0.0, 1.0]]
        receipt = ri.dual_certificate_gate(
            a_matrix=a_matrix,
            y=[2.0, 3.0],
            c=[2.0, 3.0],
            primal_objective=5.0,
            dual_objective=5.0,
        )
        self.assertEqual(receipt.verdict, ri.GateVerdict.PASS)

    def test_exponential_decay_rejects_positive_uniform_lower_bound(self):
        receipt = ri.exponential_asymptotic_gate(
            amplitude=1.0,
            exponential_rate=-0.27,
            claimed_uniform_lower_bound=1e-4,
        )
        self.assertEqual(receipt.verdict, ri.GateVerdict.FAIL)
        self.assertTrue(receipt.observation["contradiction"])

    def test_criterion_hash_is_literal_and_any_edit_opens_new_epoch(self):
        first = ri.CriterionEpoch("b ~ 0.5")
        whitespace_edit = ri.CriterionEpoch("b  ~ 0.5")
        same = ri.CriterionEpoch("b ~ 0.5")
        self.assertFalse(first.same_epoch_as(whitespace_edit))
        self.assertTrue(first.same_epoch_as(same))

    def test_admission_is_fail_closed_on_missing_receipt(self):
        basis = ri.SpectralBasis(n_f=16, h=3.5, target_gamma_max=14.13)
        with self.assertRaises(PermissionError):
            ri.AdmissionController.admit(
                stage_id="c-sweep",
                subject_digest=basis.object_digest,
                required_gate_ids=[
                    "spectral-domain-coverage",
                    "operator-decomposition-conservation",
                ],
                receipts=basis.gate_receipts,
            )

    def test_admission_rejects_spliced_receipt(self):
        basis_a = ri.SpectralBasis(n_f=16, h=3.5, target_gamma_max=14.13)
        basis_b = ri.SpectralBasis(n_f=17, h=3.5, target_gamma_max=14.13)
        with self.assertRaises(PermissionError):
            ri.AdmissionController.admit(
                stage_id="c-sweep",
                subject_digest=basis_b.object_digest,
                required_gate_ids=["spectral-domain-coverage"],
                receipts=basis_a.gate_receipts,
            )

    def test_admission_ticket_is_deterministic_except_timing(self):
        basis = ri.SpectralBasis(n_f=16, h=3.5, target_gamma_max=14.13)
        a = ri.AdmissionController.admit(
            stage_id="c-sweep",
            subject_digest=basis.object_digest,
            required_gate_ids=["spectral-domain-coverage"],
            receipts=basis.gate_receipts,
        )
        b = ri.AdmissionController.admit(
            stage_id="c-sweep",
            subject_digest=basis.object_digest,
            required_gate_ids=["spectral-domain-coverage"],
            receipts=basis.gate_receipts,
        )
        self.assertEqual(a.ticket_sha256, b.ticket_sha256)

    def test_status_type_checked_requires_pass_receipt(self):
        fail = ri.spectral_coverage_gate(12, 3.5, 14.13)
        with self.assertRaises(ValueError):
            ri.StatusRecord.type_checked("coverage", [fail])

    def test_status_computed_requires_reproducible_output_hash(self):
        epoch = ri.CriterionEpoch("z(N) grows as sqrt(N)")
        output_sha = hashlib.sha256(b"result").hexdigest()
        status = ri.StatusRecord.computed(
            claim_id="enrichment-scaling",
            output_sha256=output_sha,
            criterion_epoch=epoch,
            n=300,
            tolerance=1e-12,
            verifier_id="enrichment-scaling-v1",
        )
        self.assertEqual(status.status, ri.ResearchStatus.COMPUTED)
        self.assertEqual(status.n, 300)
        self.assertEqual(status.criterion_sha256, epoch.criterion_sha256)

    def test_theorem_requires_proof_and_checker_receipts(self):
        proof_sha = hashlib.sha256(b"proof").hexdigest()
        checker_sha = hashlib.sha256(b"checker-pass").hexdigest()
        status = ri.StatusRecord.theorem(
            claim_id="skew-quadratic-zero",
            proof_sha256=proof_sha,
            checker_receipt_sha256=checker_sha,
            verifier_id="exact-algebra-checker-v1",
        )
        self.assertEqual(status.status, ri.ResearchStatus.THEOREM)
        self.assertIsNotNone(status.evidence_sha256)


if __name__ == "__main__":
    unittest.main()
