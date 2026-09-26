import hashlib
import unittest
from dataclasses import replace

from aegis_learning.evidence_gradient_compiler_v1 import (
    CompilerPolicy,
    ExecutionStatus,
    FailureKind,
    LearningDisposition,
    VerifiedWitnessReceiptV1,
    Witness,
    WitnessStatus,
    compile_evidence_gradient,
    lz78_density_ppm,
)

HEAD = "1" * 40
BLOB = "2" * 40
POLICY_DIGEST = hashlib.sha256(b"verifier-policy-v1").hexdigest()


def _source_ref(name: str) -> str:
    return f"Aegis-Omega/AEGIS-OMEGA@{HEAD}:tests/{name}.json"


def bound_verified(name, group, *, formal=False, steps=3):
    evidence = hashlib.sha256(f"evidence:{name}".encode()).hexdigest()
    source_ref = _source_ref(name)
    receipt = VerifiedWitnessReceiptV1.build(
        source_ref=source_ref,
        source_head_sha=HEAD,
        source_blob_sha=BLOB,
        evidence_sha256=evidence,
        verifier_policy_sha256=POLICY_DIGEST,
        execution_provider="github-actions",
        execution_run_id=f"run:{name}",
        executed_steps=steps,
        execution_status=ExecutionStatus.EXECUTED_PASS,
        artifact_sha256=hashlib.sha256(f"artifact:{name}".encode()).hexdigest(),
    )
    return Witness(
        name=name,
        status=WitnessStatus.VERIFIED,
        independence_group=group,
        formal_kernel=formal,
        source_ref=source_ref,
        evidence_sha256=evidence,
        verified_receipt=receipt,
    )


def admitted_policy(*witnesses, formal=False, min_groups=2):
    return CompilerPolicy(
        min_independent_groups=min_groups,
        formal_kernel_required=formal,
        admitted_verified_receipt_sha256s=tuple(
            w.verified_receipt.receipt_sha256
            for w in witnesses
            if w.verified_receipt is not None
        ),
    )


class EvidenceGradientCompilerV1Test(unittest.TestCase):
    def test_positive_requires_receipt_bound_and_admitted_verified_witnesses(self):
        a = bound_verified("a", "analytic")
        b = bound_verified("b", "runtime")
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[a, b],
            policy=admitted_policy(a, b),
        )
        self.assertEqual(r["disposition"], LearningDisposition.POSITIVE.value)
        self.assertEqual(r["positive_gradient_weight_ppm"], 1_000_000)

    def test_well_formed_receipt_is_quarantined_without_admission(self):
        a = bound_verified("a", "analytic")
        b = bound_verified("b", "runtime")
        r = compile_evidence_gradient(
            example_id="untrusted-receipt",
            source_head_sha=HEAD,
            witnesses=[a, b],
        )
        self.assertEqual(r["disposition"], LearningDisposition.QUARANTINE.value)
        self.assertEqual(r["positive_gradient_weight_ppm"], 0)
        for row in r["witnesses"]:
            self.assertTrue(row["receipt_structurally_valid"])
            self.assertFalse(row["receipt_admitted"])
            self.assertIn("VERIFIED_RECEIPT_NOT_ADMITTED", row["provenance_errors"])

    def test_old_synthetic_verified_shape_is_quarantined(self):
        forged = Witness(
            name="forged",
            status=WitnessStatus.VERIFIED,
            independence_group="formal",
            formal_kernel=True,
            source_ref=_source_ref("forged"),
            evidence_sha256="a" * 64,
        )
        other = bound_verified("runtime", "runtime")
        r = compile_evidence_gradient(
            example_id="forgery",
            source_head_sha=HEAD,
            witnesses=[forged, other],
            policy=admitted_policy(other, formal=True),
        )
        self.assertEqual(r["disposition"], LearningDisposition.QUARANTINE.value)
        row = next(x for x in r["witnesses"] if x["name"] == "forged")
        self.assertIn("VERIFIED_RECEIPT_REQUIRED", row["provenance_errors"])

    def test_zero_step_receipt_is_quarantined(self):
        w = bound_verified("zero", "formal", formal=True)
        bad_receipt = replace(w.verified_receipt, executed_steps=0)
        bad_receipt = replace(bad_receipt, receipt_sha256=bad_receipt.computed_sha256())
        w = replace(w, verified_receipt=bad_receipt)
        runtime = bound_verified("runtime", "runtime")
        r = compile_evidence_gradient(
            example_id="zero",
            source_head_sha=HEAD,
            witnesses=[w, runtime],
            policy=CompilerPolicy(
                formal_kernel_required=True,
                admitted_verified_receipt_sha256s=(
                    bad_receipt.receipt_sha256,
                    runtime.verified_receipt.receipt_sha256,
                ),
            ),
        )
        self.assertEqual(r["disposition"], LearningDisposition.QUARANTINE.value)
        row = next(x for x in r["witnesses"] if x["name"] == "zero")
        self.assertIn("EXECUTED_STEPS_MUST_BE_POSITIVE", row["provenance_errors"])

    def test_receipt_source_ref_mismatch_is_quarantined(self):
        w = bound_verified("a", "analytic")
        bad = replace(w, source_ref=_source_ref("different"))
        b = bound_verified("b", "runtime")
        r = compile_evidence_gradient(
            example_id="mismatch",
            source_head_sha=HEAD,
            witnesses=[bad, b],
            policy=admitted_policy(w, b),
        )
        self.assertEqual(r["disposition"], LearningDisposition.QUARANTINE.value)

    def test_receipt_tampering_is_quarantined(self):
        w = bound_verified("a", "analytic")
        tampered = replace(w.verified_receipt, artifact_sha256="f" * 64)
        w = replace(w, verified_receipt=tampered)
        b = bound_verified("b", "runtime")
        r = compile_evidence_gradient(
            example_id="tamper",
            source_head_sha=HEAD,
            witnesses=[w, b],
            policy=CompilerPolicy(
                admitted_verified_receipt_sha256s=(
                    tampered.receipt_sha256,
                    b.verified_receipt.receipt_sha256,
                )
            ),
        )
        self.assertEqual(r["disposition"], LearningDisposition.QUARANTINE.value)
        row = next(x for x in r["witnesses"] if x["name"] == "a")
        self.assertIn("RECEIPT_SHA256_MISMATCH", row["provenance_errors"])

    def test_unverified_required_witness_quarantines(self):
        a = bound_verified("a", "analytic")
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[a, Witness("b", WitnessStatus.UNVERIFIED, "formal", formal_kernel=True)],
            policy=admitted_policy(a, formal=True),
        )
        self.assertEqual(r["disposition"], LearningDisposition.QUARANTINE.value)
        self.assertEqual(r["positive_gradient_weight_ppm"], 0)

    def test_semantic_disagreement_is_contrastive_not_positive(self):
        a = bound_verified("a", "analytic")
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[
                a,
                Witness(
                    "b", WitnessStatus.FAILED, "runtime",
                    failure_kind=FailureKind.SEMANTIC_DISAGREEMENT,
                    detail="observable mismatch",
                ),
            ],
            policy=admitted_policy(a),
        )
        self.assertEqual(r["disposition"], LearningDisposition.CONTRASTIVE_ONLY.value)
        self.assertEqual(r["positive_gradient_weight_ppm"], 0)
        self.assertGreater(r["contrastive_weight_ppm"], 0)

    def test_infrastructure_failure_is_quarantine_not_contrastive(self):
        a = bound_verified("a", "analytic")
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[
                a,
                Witness(
                    "runner", WitnessStatus.FAILED, "hosted",
                    failure_kind=FailureKind.INFRASTRUCTURE,
                    detail="zero-step runner",
                ),
            ],
            policy=admitted_policy(a),
        )
        self.assertEqual(r["disposition"], LearningDisposition.QUARANTINE.value)

    def test_formal_policy_needs_admitted_receipt_bound_kernel_witness(self):
        a = bound_verified("a", "analytic")
        b = bound_verified("b", "runtime")
        no_formal = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[a, b],
            policy=admitted_policy(a, b, formal=True),
        )
        self.assertEqual(no_formal["disposition"], LearningDisposition.QUARANTINE.value)

        lean = bound_verified("lean", "formal", formal=True)
        yes_formal = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[a, lean],
            policy=admitted_policy(a, lean, formal=True),
        )
        self.assertEqual(yes_formal["disposition"], LearningDisposition.POSITIVE.value)
        self.assertTrue(yes_formal["formal_kernel_verified"])

    def test_invalid_admitted_receipt_digest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ADMITTED_RECEIPT_SHA256_INVALID"):
            CompilerPolicy(admitted_verified_receipt_sha256s=("not-a-digest",)).validate()

    def test_lz_volatility_changes_priority_not_authority(self):
        a = bound_verified("a", "analytic")
        b = bound_verified("b", "runtime")
        policy = admitted_policy(a, b)
        stable = compile_evidence_gradient(
            example_id="x", source_head_sha=HEAD, witnesses=[a, b], policy=policy,
            representation=b"aaaaaaaaaaaaaaaa", previous_representation=b"aaaaaaaaaaaaaaaa",
        )
        volatile = compile_evidence_gradient(
            example_id="y", source_head_sha=HEAD, witnesses=[a, b], policy=policy,
            representation=bytes(range(16)), previous_representation=b"aaaaaaaaaaaaaaaa",
        )
        self.assertEqual(stable["disposition"], LearningDisposition.POSITIVE.value)
        self.assertEqual(volatile["disposition"], LearningDisposition.POSITIVE.value)
        self.assertGreaterEqual(volatile["sampling_priority_ppm"], stable["sampling_priority_ppm"])

    def test_receipt_hash_deterministic(self):
        a = bound_verified("a", "analytic")
        b = bound_verified("b", "runtime")
        kwargs = dict(
            example_id="x", source_head_sha=HEAD, witnesses=[a, b],
            representation=b"same", policy=admitted_policy(a, b),
        )
        first = compile_evidence_gradient(**kwargs)
        second = compile_evidence_gradient(**kwargs)
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])

    def test_lz_density_is_bounded(self):
        for data in (b"", b"a", b"aaaa", bytes(range(32))):
            self.assertGreaterEqual(lz78_density_ppm(data), 0)
            self.assertLessEqual(lz78_density_ppm(data), 1_000_000)


if __name__ == "__main__":
    unittest.main()