from __future__ import annotations

import hashlib

from harness.sdk.meaning_heritage import (
    ClaimRef,
    ClaimSetEnvelopeV1,
    ClaimSetVerifierV13,
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
    def __init__(self, claim: ClaimRef, name: str) -> None:
        self.claim = claim
        self.extractor_root = h("FP_EXTRACTOR", name)
        self.policy_root = h("FP_POLICY", name)

    def extract(self, payload: bytes) -> tuple[ClaimRef, ...]:
        return (self.claim,)


class ProofStore:
    def __init__(self) -> None:
        self.preservation = {}

    def fetch_preservation(self, root: str):
        return self.preservation.get(root)

    def fetch_derivation(self, root: str):
        return None


def issue(payload: bytes, claim: ClaimRef, name: str):
    extractor = FixedExtractor(claim, name)
    envelope = ClaimSetEnvelopeV1(
        lineage_id=name,
        payload_root=hashlib.sha256(payload).hexdigest(),
        raw_claims=(claim,),
        extractor_root=extractor.extractor_root,
        extractor_policy_root=extractor.policy_root,
    )
    return ClaimSetVerifierV13.verify_and_issue(envelope, payload, extractor)


def test_preservation_receipt_fingerprint_must_match_authenticated_claimsets():
    digest = h("CLAIM", {"statement": "same semantic subject"})
    source_claim = ClaimRef("source", digest, "fp:source-authenticated")
    derived_claim = ClaimRef("derived", digest, "fp:derived-authenticated")
    source = issue(b"source-payload", source_claim, "source")
    derived = issue(b"derived-payload", derived_claim, "derived")

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
    )
    result, receipt = verifier.verify(envelope, source, derived)
    assert receipt is None
    assert "PRESERVATION_PROOF_FINGERPRINT_MISMATCH" in result.error_codes
