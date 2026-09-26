import hashlib
import unittest

from aegis_learning.evidence_gradient_compiler_v1 import (
    CompilerPolicy,
    FailureKind,
    LearningDisposition,
    Witness,
    WitnessStatus,
    compile_evidence_gradient,
    lz78_density_ppm,
)

HEAD = "1" * 40
DIGEST = hashlib.sha256(b"evidence").hexdigest()


def verified(name, group, *, formal=False):
    return Witness(
        name=name,
        status=WitnessStatus.VERIFIED,
        independence_group=group,
        formal_kernel=formal,
        source_ref=f"repo@{HEAD}:{name}",
        evidence_sha256=DIGEST,
    )


class EvidenceGradientCompilerV1Test(unittest.TestCase):
    def test_positive_requires_all_required_verified(self):
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[verified("a", "analytic"), verified("b", "runtime")],
        )
        self.assertEqual(r["disposition"], LearningDisposition.POSITIVE.value)
        self.assertEqual(r["positive_gradient_weight_ppm"], 1_000_000)

    def test_unverified_required_witness_quarantines(self):
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[
                verified("a", "analytic"),
                Witness(
                    "b", WitnessStatus.UNVERIFIED, "formal",
                    formal_kernel=True,
                ),
            ],
            policy=CompilerPolicy(formal_kernel_required=True),
        )
        self.assertEqual(
            r["disposition"], LearningDisposition.QUARANTINE.value
        )
        self.assertEqual(r["positive_gradient_weight_ppm"], 0)

    def test_semantic_disagreement_is_contrastive_not_positive(self):
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[
                verified("a", "analytic"),
                Witness(
                    "b", WitnessStatus.FAILED, "runtime",
                    failure_kind=FailureKind.SEMANTIC_DISAGREEMENT,
                    detail="observable mismatch",
                ),
            ],
        )
        self.assertEqual(
            r["disposition"], LearningDisposition.CONTRASTIVE_ONLY.value
        )
        self.assertEqual(r["positive_gradient_weight_ppm"], 0)
        self.assertGreater(r["contrastive_weight_ppm"], 0)

    def test_infrastructure_failure_is_quarantine_not_contrastive(self):
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[
                verified("a", "analytic"),
                Witness(
                    "runner", WitnessStatus.FAILED, "hosted",
                    failure_kind=FailureKind.INFRASTRUCTURE,
                    detail="zero-step runner",
                ),
            ],
        )
        self.assertEqual(
            r["disposition"], LearningDisposition.QUARANTINE.value
        )

    def test_formal_policy_needs_kernel_verified_witness(self):
        no_formal = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[verified("a", "analytic"), verified("b", "runtime")],
            policy=CompilerPolicy(formal_kernel_required=True),
        )
        self.assertEqual(
            no_formal["disposition"], LearningDisposition.QUARANTINE.value
        )

        yes_formal = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[
                verified("a", "analytic"),
                verified("lean", "formal", formal=True),
            ],
            policy=CompilerPolicy(formal_kernel_required=True),
        )
        self.assertEqual(
            yes_formal["disposition"], LearningDisposition.POSITIVE.value
        )

    def test_verified_without_provenance_quarantines(self):
        r = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[
                verified("a", "analytic"),
                Witness("b", WitnessStatus.VERIFIED, "runtime"),
            ],
        )
        self.assertEqual(
            r["disposition"], LearningDisposition.QUARANTINE.value
        )

    def test_lz_volatility_changes_priority_not_authority(self):
        stable = compile_evidence_gradient(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[verified("a", "analytic"), verified("b", "runtime")],
            representation=b"aaaaaaaaaaaaaaaa",
            previous_representation=b"aaaaaaaaaaaaaaaa",
        )
        volatile = compile_evidence_gradient(
            example_id="y",
            source_head_sha=HEAD,
            witnesses=[verified("a", "analytic"), verified("b", "runtime")],
            representation=bytes(range(16)),
            previous_representation=b"aaaaaaaaaaaaaaaa",
        )
        self.assertEqual(
            stable["disposition"], LearningDisposition.POSITIVE.value
        )
        self.assertEqual(
            volatile["disposition"], LearningDisposition.POSITIVE.value
        )
        self.assertGreaterEqual(
            volatile["sampling_priority_ppm"],
            stable["sampling_priority_ppm"],
        )

    def test_receipt_hash_deterministic(self):
        kwargs = dict(
            example_id="x",
            source_head_sha=HEAD,
            witnesses=[verified("a", "analytic"), verified("b", "runtime")],
            representation=b"same",
        )
        a = compile_evidence_gradient(**kwargs)
        b = compile_evidence_gradient(**kwargs)
        self.assertEqual(a["receipt_sha256"], b["receipt_sha256"])

    def test_lz_density_is_bounded(self):
        for data in (b"", b"a", b"aaaa", bytes(range(32))):
            self.assertGreaterEqual(lz78_density_ppm(data), 0)
            self.assertLessEqual(lz78_density_ppm(data), 1_000_000)


if __name__ == "__main__":
    unittest.main()
