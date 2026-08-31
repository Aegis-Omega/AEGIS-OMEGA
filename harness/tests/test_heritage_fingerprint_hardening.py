from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from harness.sdk.meaning_heritage import (
    ClaimRef,
    ClaimSetEnvelopeV1,
    ClaimSetReceiptV1,
    ClaimSetVerifierV13,
    DeclaredAdditionEdge,
    DerivationProofReceiptV1,
    HeritageError,
    HeritageVerifierV13,
    LossType,
    PreservationEdge,
    PreservationProofReceiptV1,
    PreservationRelation,
    SemanticLineageEnvelopeV1,
    TransformRelation,
    canonical_hash,
)


def h(domain: str, value: object) -> str:
    return canonical_hash(domain, value)


class FixedExtractor:
    def __init__(self, claims: tuple[ClaimRef, ...], name: str) -> None:
        self.claims = claims
        self.extractor_root = h("FP_EXTRACTOR", name)
        self.policy_root = h("FP_POLICY", name)

    def extract(self, payload: bytes) -> tuple[ClaimRef, ...]:
        return self.claims


class ProofStore:
    def __init__(self) -> None:
        self.preservation = {}
        self.derivation = {}

    def fetch_preservation(self, root: str):
        return self.preservation.get(root)

    def fetch_derivation(self, root: str):
        return self.derivation.get(root)


class ClaimSetStore:
    def __init__(self, *receipts: ClaimSetReceiptV1) -> None:
        self.data = {receipt.root: receipt for receipt in receipts}

    def fetch_verified(self, root: str):
        return self.data.get(root)


def issue(payload: bytes, claims: tuple[ClaimRef, ...], name: str):
    extractor = FixedExtractor(claims, name)
    envelope = ClaimSetEnvelopeV1(
        lineage_id=name,
        payload_root=hashlib.sha256(payload).hexdigest(),
        raw_claims=claims,
        extractor_root=extractor.extractor_root,
        extractor_policy_root=extractor.policy_root,
    )
    return ClaimSetVerifierV13.verify_and_issue(envelope, payload, extractor)


def test_preservation_receipt_fingerprint_must_match_authenticated_claimsets():
    digest = h("CLAIM", {"statement": "same semantic subject"})
    source_claim = ClaimRef("source", digest, "fp:source-authenticated")
    derived_claim = ClaimRef("derived", digest, "fp:derived-authenticated")
    source = issue(b"source-payload", (source_claim,), "source")
    derived = issue(b"derived-payload", (derived_claim,), "derived")

    proof = PreservationProofReceiptV1(
        source_claim_digest=digest,
        derived_claim_digest=digest,
        relation=PreservationRelation.SEMANTIC_EQUIVALENCE,
        source_semantic_fingerprint="fp:forged-source",
        derived_semantic_fingerprint="fp:forged-derived",
        verifier_root=h("SEMANTIC_VERIFIER", 1),
        policy_root=h("SEMANTIC_POLICY", 1),
    )
    store = ProofStore()
    store.preservation[proof.root] = proof

    envelope = SemanticLineageEnvelopeV1(
        lineage_id="fingerprint-splice",
        source_root=source.payload_root,
        source_claimset_receipt_root=source.root,
        derived_root=derived.payload_root,
        derived_claimset_receipt_root=derived.root,
        transform_root=h("TRANSFORM", 1),
        transform_relation=TransformRelation.LOSSY_TRANSFORM,
        loss_type=LossType.HEURISTIC_ABSTRACTION,
        preservation_edges=(
            PreservationEdge(
                digest,
                digest,
                PreservationRelation.SEMANTIC_EQUIVALENCE,
                proof.root,
            ),
        ),
        declared_omission_digests=(),
        declared_additions=(),
        uncertainty_bps=100,
    )
    verifier = HeritageVerifierV13(
        verifier_root=h("HERITAGE_VERIFIER", 1),
        policy_root=h("HERITAGE_POLICY", 1),
        proof_store=store,
        claimset_store=ClaimSetStore(source, derived),
    )
    result, receipt = verifier.verify(envelope, source, derived)
    assert receipt is None
    assert "PRESERVATION_PROOF_FINGERPRINT_MISMATCH" in result.error_codes


def test_derivation_receipt_must_bind_source_and_derived_semantic_fingerprints():
    a_digest = h("CLAIM", {"statement": "premise A"})
    b_digest = h("CLAIM", {"statement": "derived B"})
    source_a = ClaimRef("A", a_digest, "fp:A-authenticated")
    derived_a = ClaimRef("A", a_digest, "fp:A-authenticated")
    derived_b = ClaimRef("B", b_digest, "fp:B-authenticated")
    source = issue(b"source-A", (source_a,), "source-A")
    derived = issue(b"derived-A-B", (derived_a, derived_b), "derived-A-B")

    store = ProofStore()
    preservation = PreservationProofReceiptV1(
        source_claim_digest=a_digest,
        derived_claim_digest=a_digest,
        relation=PreservationRelation.SAME_CLAIM_ROOT,
        source_semantic_fingerprint=source_a.semantic_fingerprint,
        derived_semantic_fingerprint=derived_a.semantic_fingerprint,
        verifier_root=h("SEMANTIC_VERIFIER", "preserve-A"),
        policy_root=h("SEMANTIC_POLICY", "preserve-A"),
    )
    store.preservation[preservation.root] = preservation

    transform_root = h("TRANSFORM", "augment-A-to-B")
    forged_derivation = DerivationProofReceiptV1(
        derived_claim_digest=b_digest,
        source_claim_digests=(a_digest,),
        source_semantic_fingerprints=("fp:A-forged",),
        derived_semantic_fingerprint="fp:B-forged",
        transform_root=transform_root,
        verifier_root=h("DERIVATION_VERIFIER", 1),
        policy_root=h("DERIVATION_POLICY", 1),
    )
    store.derivation[forged_derivation.root] = forged_derivation

    envelope = SemanticLineageEnvelopeV1(
        lineage_id="derivation-fingerprint-splice",
        source_root=source.payload_root,
        source_claimset_receipt_root=source.root,
        derived_root=derived.payload_root,
        derived_claimset_receipt_root=derived.root,
        transform_root=transform_root,
        transform_relation=TransformRelation.AUGMENTING_TRANSFORM,
        loss_type=LossType.EXACT_LOSSLESS,
        preservation_edges=(
            PreservationEdge(
                a_digest,
                a_digest,
                PreservationRelation.SAME_CLAIM_ROOT,
                preservation.root,
            ),
        ),
        declared_omission_digests=(),
        declared_additions=(DeclaredAdditionEdge(b_digest, forged_derivation.root),),
        uncertainty_bps=0,
    )
    verifier = HeritageVerifierV13(
        verifier_root=h("HERITAGE_VERIFIER", 2),
        policy_root=h("HERITAGE_POLICY", 2),
        proof_store=store,
        claimset_store=ClaimSetStore(source, derived),
    )
    result, receipt = verifier.verify(envelope, source, derived)
    assert receipt is None
    assert "DERIVATION_PROOF_FINGERPRINT_MISMATCH" in result.error_codes

    valid_derivation = DerivationProofReceiptV1(
        derived_claim_digest=b_digest,
        source_claim_digests=(a_digest,),
        source_semantic_fingerprints=(source_a.semantic_fingerprint,),
        derived_semantic_fingerprint=derived_b.semantic_fingerprint,
        transform_root=transform_root,
        verifier_root=h("DERIVATION_VERIFIER", 1),
        policy_root=h("DERIVATION_POLICY", 1),
    )
    assert valid_derivation.root != forged_derivation.root
    store.derivation[valid_derivation.root] = valid_derivation
    valid_envelope = replace(
        envelope,
        declared_additions=(DeclaredAdditionEdge(b_digest, valid_derivation.root),),
    )
    result2, receipt2 = verifier.verify(valid_envelope, source, derived)
    assert result2.status == "PASS"
    assert receipt2 is not None


def test_claimset_receipts_must_be_trusted_not_merely_self_consistent():
    claim = ClaimRef(
        "forged",
        h("CLAIM", {"statement": "fabricated without extractor replay"}),
        "fp:forged-claimset",
    )
    forged = ClaimSetReceiptV1(
        claimset_envelope_root=h("FORGED_CLAIMSET_ENVELOPE", 1),
        payload_root=h("FORGED_PAYLOAD", 1),
        extractor_root=h("FORGED_EXTRACTOR", 1),
        extractor_policy_root=h("FORGED_EXTRACTOR_POLICY", 1),
        claimset_root=h("FORGED_CLAIMSET", 1),
        sorted_claims=(claim,),
        verification_root=h("FORGED_CLAIMSET_VERIFICATION", 1),
    )
    proof = PreservationProofReceiptV1(
        source_claim_digest=claim.claim_digest,
        derived_claim_digest=claim.claim_digest,
        relation=PreservationRelation.SAME_CLAIM_ROOT,
        source_semantic_fingerprint=claim.semantic_fingerprint,
        derived_semantic_fingerprint=claim.semantic_fingerprint,
        verifier_root=h("SEMANTIC_VERIFIER", "forged-claimset"),
        policy_root=h("SEMANTIC_POLICY", "forged-claimset"),
    )
    store = ProofStore()
    store.preservation[proof.root] = proof
    envelope = SemanticLineageEnvelopeV1(
        lineage_id="forged-claimset-receipt",
        source_root=forged.payload_root,
        source_claimset_receipt_root=forged.root,
        derived_root=forged.payload_root,
        derived_claimset_receipt_root=forged.root,
        transform_root=h("IDENTITY_TRANSFORM", 1),
        transform_relation=TransformRelation.IDENTITY,
        loss_type=LossType.EXACT_LOSSLESS,
        preservation_edges=(
            PreservationEdge(
                claim.claim_digest,
                claim.claim_digest,
                PreservationRelation.SAME_CLAIM_ROOT,
                proof.root,
            ),
        ),
        declared_omission_digests=(),
        declared_additions=(),
        uncertainty_bps=0,
    )
    verifier = HeritageVerifierV13(
        verifier_root=h("HERITAGE_VERIFIER", "forged-claimset"),
        policy_root=h("HERITAGE_POLICY", "forged-claimset"),
        proof_store=store,
        claimset_store=ClaimSetStore(),
    )
    result, receipt = verifier.verify(envelope, forged, forged)
    assert receipt is None
    assert "CLAIMSET_RECEIPT_UNTRUSTED" in result.error_codes


def test_same_claim_root_requires_same_semantic_fingerprint():
    digest = h("CLAIM", {"statement": "same digest, different semantic contexts"})
    with pytest.raises(HeritageError, match="SAME_CLAIM_ROOT_FINGERPRINT_MISMATCH"):
        PreservationProofReceiptV1(
            source_claim_digest=digest,
            derived_claim_digest=digest,
            relation=PreservationRelation.SAME_CLAIM_ROOT,
            source_semantic_fingerprint="fp:carrier-A",
            derived_semantic_fingerprint="fp:carrier-B",
            verifier_root=h("SEMANTIC_VERIFIER", "same-root-context"),
            policy_root=h("SEMANTIC_POLICY", "same-root-context"),
        )


def test_preserved_source_cannot_also_be_declared_omitted():
    digest = h("CLAIM", "overlap-source")
    edge = PreservationEdge(
        digest,
        digest,
        PreservationRelation.SAME_CLAIM_ROOT,
        h("PRESERVATION_PROOF", "overlap-source"),
    )
    with pytest.raises(HeritageError, match="PRESERVATION_OMISSION_OVERLAP"):
        SemanticLineageEnvelopeV1(
            lineage_id="preserved-and-omitted",
            source_root=h("PAYLOAD", "source"),
            source_claimset_receipt_root=h("CLAIMSET_RECEIPT", "source"),
            derived_root=h("PAYLOAD", "derived"),
            derived_claimset_receipt_root=h("CLAIMSET_RECEIPT", "derived"),
            transform_root=h("TRANSFORM", "overlap-source"),
            transform_relation=TransformRelation.LOSSY_TRANSFORM,
            loss_type=LossType.HEURISTIC_ABSTRACTION,
            preservation_edges=(edge,),
            declared_omission_digests=(digest,),
            declared_additions=(),
            uncertainty_bps=100,
        )


def test_preserved_derived_cannot_also_be_declared_added():
    digest = h("CLAIM", "overlap-derived")
    edge = PreservationEdge(
        digest,
        digest,
        PreservationRelation.SAME_CLAIM_ROOT,
        h("PRESERVATION_PROOF", "overlap-derived"),
    )
    with pytest.raises(HeritageError, match="PRESERVATION_ADDITION_OVERLAP"):
        SemanticLineageEnvelopeV1(
            lineage_id="preserved-and-added",
            source_root=h("PAYLOAD", "source2"),
            source_claimset_receipt_root=h("CLAIMSET_RECEIPT", "source2"),
            derived_root=h("PAYLOAD", "derived2"),
            derived_claimset_receipt_root=h("CLAIMSET_RECEIPT", "derived2"),
            transform_root=h("TRANSFORM", "overlap-derived"),
            transform_relation=TransformRelation.AUGMENTING_TRANSFORM,
            loss_type=LossType.EXACT_LOSSLESS,
            preservation_edges=(edge,),
            declared_omission_digests=(),
            declared_additions=(
                DeclaredAdditionEdge(digest, h("DERIVATION_PROOF", "overlap-derived")),
            ),
            uncertainty_bps=0,
        )
