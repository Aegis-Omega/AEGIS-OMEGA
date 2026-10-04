from __future__ import annotations

import hashlib
from dataclasses import asdict, replace

import pytest

from harness.sdk.meaning_heritage import (
    ClaimRef,
    ClaimSetEnvelopeV1,
    ClaimSetReceiptV1,
    ClaimSetVerifierV13,
    HeritageError,
    HeritageReceiptV1,
    HeritageVerifierV13,
    LossType,
    PreservationEdge,
    PreservationProofReceiptV1,
    PreservationRelation,
    SemanticLineageEnvelopeV1,
    TransformRelation,
    canonical_hash,
)
from harness.sdk.morphisms import (
    CarrierProofObligationV1,
    CarrierVerifierV1,
    CompositionProofReceiptV1,
    HeritageMorphismVerifierV1,
    LimitVerifierV1,
    MorphismEnvelopeV1,
    MorphismError,
    MorphismKind,
    MorphismVerifierRegistryV1,
    ProofArtifactKind,
    ProofArtifactReceiptV1,
    RepresentationVerifierV1,
    SemanticVerifierV1,
    SpaceProofObligationV1,
    SpaceVerifierV1,
    TheoremContextV1,
)


def h(domain: str, value: object) -> str:
    return canonical_hash(domain, value)


class FixedExtractor:
    def __init__(self, claims: tuple[ClaimRef, ...], *, name: str = "fixed") -> None:
        self._claims = claims
        self.extractor_root = h("TEST_EXTRACTOR", {"name": name})
        self.policy_root = h("TEST_EXTRACTOR_POLICY", {"name": name})

    def extract(self, payload: bytes) -> tuple[ClaimRef, ...]:
        return self._claims


class SemanticProofStore:
    def __init__(self) -> None:
        self.preservation: dict[str, PreservationProofReceiptV1] = {}
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


class HeritageStore:
    def __init__(self) -> None:
        self.data: dict[str, HeritageReceiptV1] = {}

    def fetch_verified(self, root: str):
        return self.data.get(root)


class ProofStore:
    def __init__(self) -> None:
        self.data: dict[str, ProofArtifactReceiptV1] = {}

    def fetch_verified(self, root: str):
        return self.data.get(root)

    def put(self, receipt: ProofArtifactReceiptV1) -> str:
        self.data[receipt.root] = receipt
        return receipt.root


class MorphismStore:
    def __init__(self) -> None:
        self.data = {}

    def fetch_verified(self, root: str):
        return self.data.get(root)

    def put(self, receipt):
        self.data[receipt.root] = receipt
        return receipt.root


class CompositionStore:
    def __init__(self) -> None:
        self.data: dict[str, CompositionProofReceiptV1] = {}

    def fetch_verified(self, root: str):
        return self.data.get(root)

    def put(self, receipt: CompositionProofReceiptV1) -> str:
        self.data[receipt.root] = receipt
        return receipt.root


def claim(name: str) -> ClaimRef:
    return ClaimRef(name, h("TEST_CLAIM", {"name": name}), f"fp:{name}")


def issue_claimset(payload: bytes, claims: tuple[ClaimRef, ...], lineage: str):
    extractor = FixedExtractor(claims, name=lineage)
    env = ClaimSetEnvelopeV1(
        lineage_id=lineage,
        payload_root=hashlib.sha256(payload).hexdigest(),
        raw_claims=claims,
        extractor_root=extractor.extractor_root,
        extractor_policy_root=extractor.policy_root,
    )
    return env, ClaimSetVerifierV13.verify_and_issue(env, payload, extractor)


def proof_receipt(kind: ProofArtifactKind, subject_root: str, salt: str) -> ProofArtifactReceiptV1:
    return ProofArtifactReceiptV1(
        proof_kind=kind,
        subject_root=subject_root,
        verifier_root=h("TEST_PROOF_VERIFIER", salt),
        policy_root=h("TEST_PROOF_POLICY", salt),
        status="PASS",
        proof_context_root=h("TEST_PROOF_CONTEXT", salt),
    )


def test_claimset_extraction_mismatch_fails_closed():
    payload = b"payload"
    declared = (claim("A"),)
    actual = (claim("B"),)
    extractor = FixedExtractor(actual, name="mismatch")
    env = ClaimSetEnvelopeV1(
        lineage_id="lin",
        payload_root=hashlib.sha256(payload).hexdigest(),
        raw_claims=declared,
        extractor_root=extractor.extractor_root,
        extractor_policy_root=extractor.policy_root,
    )
    with pytest.raises(HeritageError, match="CLAIMSET_EXTRACTION_MISMATCH"):
        ClaimSetVerifierV13.verify_and_issue(env, payload, extractor)


def test_duplicate_claim_digest_rejected_at_runtime():
    c = claim("A")
    with pytest.raises(HeritageError, match="DUPLICATE_CLAIM_DIGEST"):
        ClaimSetEnvelopeV1(
            lineage_id="lin",
            payload_root=hashlib.sha256(b"x").hexdigest(),
            raw_claims=(c, c),
            extractor_root=h("EX", 1),
            extractor_policy_root=h("POL", 1),
        )


def test_heritage_semantic_proof_must_be_authenticated_and_input_bound():
    source_payload = b"source"
    derived_payload = b"derived"
    a = claim("A")
    b = claim("B")
    _, src = issue_claimset(source_payload, (a,), "src")
    _, der = issue_claimset(derived_payload, (b,), "der")

    proof_store = SemanticProofStore()
    verifier = HeritageVerifierV13(
        verifier_root=h("HERITAGE_VERIFIER", 1),
        policy_root=h("HERITAGE_POLICY", 1),
        proof_store=proof_store,
        claimset_store=ClaimSetStore(src, der),
    )
    fake_root = h("FAKE_PROOF", 1)
    env = SemanticLineageEnvelopeV1(
        lineage_id="lin",
        source_root=src.payload_root,
        source_claimset_receipt_root=src.root,
        derived_root=der.payload_root,
        derived_claimset_receipt_root=der.root,
        transform_root=h("TRANSFORM", 1),
        transform_relation=TransformRelation.LOSSY_TRANSFORM,
        loss_type=LossType.HEURISTIC_ABSTRACTION,
        preservation_edges=(
            PreservationEdge(
                a.claim_digest,
                b.claim_digest,
                PreservationRelation.SEMANTIC_EQUIVALENCE,
                fake_root,
            ),
        ),
        declared_omission_digests=(),
        declared_additions=(),
        uncertainty_bps=100,
    )
    result, receipt = verifier.verify(env, src, der)
    assert receipt is None
    assert "PRESERVATION_PROOF_UNTRUSTED" in result.error_codes

    proof = PreservationProofReceiptV1(
        source_claim_digest=a.claim_digest,
        derived_claim_digest=b.claim_digest,
        relation=PreservationRelation.SEMANTIC_EQUIVALENCE,
        source_semantic_fingerprint=a.semantic_fingerprint,
        derived_semantic_fingerprint=b.semantic_fingerprint,
        verifier_root=h("SEMANTIC_VERIFIER", 1),
        policy_root=h("SEMANTIC_POLICY", 1),
    )
    proof_store.preservation[proof.root] = proof
    env2 = replace(
        env,
        preservation_edges=(
            PreservationEdge(
                a.claim_digest,
                b.claim_digest,
                PreservationRelation.SEMANTIC_EQUIVALENCE,
                proof.root,
            ),
        ),
    )
    result2, receipt2 = verifier.verify(env2, src, der)
    assert result2.status == "PASS"
    assert receipt2 is not None

    result3, receipt3 = verifier.verify(replace(env2, lineage_id="lin-other"), src, der)
    assert receipt3 is not None
    assert result2.verification_root != result3.verification_root


def test_predecessors_require_trusted_store():
    payload = b"same"
    a = claim("A")
    _, rec = issue_claimset(payload, (a,), "same")
    proof_store = SemanticProofStore()
    proof = PreservationProofReceiptV1(
        source_claim_digest=a.claim_digest,
        derived_claim_digest=a.claim_digest,
        relation=PreservationRelation.SAME_CLAIM_ROOT,
        source_semantic_fingerprint=a.semantic_fingerprint,
        derived_semantic_fingerprint=a.semantic_fingerprint,
        verifier_root=h("SEMVER", 1),
        policy_root=h("SEMPOL", 1),
    )
    proof_store.preservation[proof.root] = proof
    env = SemanticLineageEnvelopeV1(
        lineage_id="identity",
        source_root=rec.payload_root,
        source_claimset_receipt_root=rec.root,
        derived_root=rec.payload_root,
        derived_claimset_receipt_root=rec.root,
        transform_root=h("IDENTITY", 1),
        transform_relation=TransformRelation.IDENTITY,
        loss_type=LossType.EXACT_LOSSLESS,
        preservation_edges=(
            PreservationEdge(
                a.claim_digest,
                a.claim_digest,
                PreservationRelation.SAME_CLAIM_ROOT,
                proof.root,
            ),
        ),
        declared_omission_digests=(),
        declared_additions=(),
        uncertainty_bps=0,
    )
    verifier = HeritageVerifierV13(
        verifier_root=h("HV", 1),
        policy_root=h("HP", 1),
        proof_store=proof_store,
        claimset_store=ClaimSetStore(rec),
    )
    _, first = verifier.verify(env, rec, rec)
    assert first is not None
    result, second = verifier.verify(env, rec, rec, (first,))
    assert second is None
    assert "TRUST_STORE_REQUIRED" in result.error_codes


def test_v13_verifier_cannot_accept_caller_authored_composite_envelope():
    payload = b"same"
    a = claim("A")
    _, rec = issue_claimset(payload, (a,), "legacy-compose")
    proof_store = SemanticProofStore()
    proof = PreservationProofReceiptV1(
        source_claim_digest=a.claim_digest,
        derived_claim_digest=a.claim_digest,
        relation=PreservationRelation.SAME_CLAIM_ROOT,
        source_semantic_fingerprint=a.semantic_fingerprint,
        derived_semantic_fingerprint=a.semantic_fingerprint,
        verifier_root=h("SEMVER", "legacy-compose"),
        policy_root=h("SEMPOL", "legacy-compose"),
    )
    proof_store.preservation[proof.root] = proof
    claimsets = ClaimSetStore(rec)
    heritage = HeritageStore()
    verifier = HeritageVerifierV13(
        verifier_root=h("HV", "legacy-compose"),
        policy_root=h("HP", "legacy-compose"),
        proof_store=proof_store,
        claimset_store=claimsets,
        heritage_store=heritage,
    )

    def identity_envelope(salt: str) -> SemanticLineageEnvelopeV1:
        return SemanticLineageEnvelopeV1(
            lineage_id=f"identity:{salt}",
            source_root=rec.payload_root,
            source_claimset_receipt_root=rec.root,
            derived_root=rec.payload_root,
            derived_claimset_receipt_root=rec.root,
            transform_root=h("IDENTITY", salt),
            transform_relation=TransformRelation.IDENTITY,
            loss_type=LossType.EXACT_LOSSLESS,
            preservation_edges=(
                PreservationEdge(
                    a.claim_digest,
                    a.claim_digest,
                    PreservationRelation.SAME_CLAIM_ROOT,
                    proof.root,
                ),
            ),
            declared_omission_digests=(),
            declared_additions=(),
            uncertainty_bps=0,
        )

    _, h1 = verifier.verify(identity_envelope("h1"), rec, rec)
    _, h2 = verifier.verify(identity_envelope("h2"), rec, rec)
    assert h1 is not None
    assert h2 is not None
    heritage.data[h1.root] = h1
    heritage.data[h2.root] = h2

    caller_authored = identity_envelope("caller-authored-composite")
    with pytest.raises(AttributeError, match="compose"):
        verifier.compose(h1, h2, caller_authored, rec, rec)


def make_registry(proof_store: ProofStore, heritage_store: HeritageStore):
    common = dict(
        verifier_root=h("VERIFIER", 1),
        policy_root=h("POLICY", 1),
        proof_store=proof_store,
    )
    return MorphismVerifierRegistryV1(
        (
            CarrierVerifierV1(**common),
            SpaceVerifierV1(**common),
            RepresentationVerifierV1(**common),
            LimitVerifierV1(**common),
            SemanticVerifierV1(**common),
            HeritageMorphismVerifierV1(
                verifier_root=h("HERITAGE_MORPHISM_VERIFIER", 1),
                policy_root=h("HERITAGE_MORPHISM_POLICY", 1),
                heritage_store=heritage_store,
            ),
        )
    )


def test_kind_obligation_mismatch_rejected():
    space = SpaceProofObligationV1(
        subject_root=h("SUBJECT", 1),
        source_space_root=h("SPACE", "A"),
        target_space_root=h("SPACE", "B"),
        image_membership_receipt_root=h("R", 1),
        admissibility_receipt_root=h("R", 2),
    )
    with pytest.raises(MorphismError, match="MORPHISM_KIND_OBLIGATION_MISMATCH"):
        MorphismEnvelopeV1(
            morphism_id="bad",
            kind=MorphismKind.CARRIER,
            source_domain_root=h("D", "A"),
            target_domain_root=h("D", "B"),
            proof_obligation=space,
        )


def test_carrier_requires_authenticated_subject_bound_proof():
    store = ProofStore()
    registry = make_registry(store, HeritageStore())
    source = TheoremContextV1(
        h("T", 1), h("C", 1), h("H", 1), h("N", 1), h("G", 1)
    )
    target = TheoremContextV1(
        h("T", 2), h("C", 2), h("H", 2), h("N", 2), h("G", 2)
    )
    transport_map = h("MAP", 1)
    subject = h(
        "AEGIS_CARRIER_TRANSPORT_SUBJECT_V1",
        {
            "source": asdict(source),
            "target": asdict(target),
            "transport_map_root": transport_map,
        },
    )
    proof = proof_receipt(ProofArtifactKind.CARRIER_TRANSPORT, subject, "carrier")
    proof_root = store.put(proof)
    env = MorphismEnvelopeV1(
        "carrier-1",
        MorphismKind.CARRIER,
        source.carrier_root,
        target.carrier_root,
        CarrierProofObligationV1(source, target, transport_map, proof_root),
    )
    result, receipt = registry.verify_and_issue(env)
    assert result.status == "PASS"
    assert receipt is not None
    assert receipt.authority_class == "NONE"


def test_composition_requires_trusted_predecessors_and_endpoint_match():
    store = ProofStore()
    morph_store = MorphismStore()
    comp_store = CompositionStore()
    registry = make_registry(store, HeritageStore())

    a, b, c = h("D", "A"), h("D", "B"), h("D", "C")

    def make_space(mid: str, src: str, dst: str):
        subject_root = h("SUBJECT", mid)
        proof_subject = h(
            "AEGIS_SPACE_SUBJECT_V1",
            {
                "subject_root": subject_root,
                "source_space_root": src,
                "target_space_root": dst,
            },
        )
        image = proof_receipt(
            ProofArtifactKind.SPACE_IMAGE_MEMBERSHIP,
            proof_subject,
            mid + "i",
        )
        adm = proof_receipt(
            ProofArtifactKind.SPACE_ADMISSIBILITY,
            proof_subject,
            mid + "a",
        )
        store.put(image)
        store.put(adm)
        return MorphismEnvelopeV1(
            f"space-{mid}",
            MorphismKind.SPACE,
            src,
            dst,
            SpaceProofObligationV1(subject_root, src, dst, image.root, adm.root),
        )

    e1 = make_space("1", a, b)
    e2 = make_space("2", b, c)
    _, r1 = registry.verify_and_issue(e1)
    _, r2 = registry.verify_and_issue(e2)
    assert r1 and r2
    morph_store.put(r1)
    morph_store.put(r2)

    composed = make_space("comp", a, c)
    comp_proof = CompositionProofReceiptV1(
        left_morphism_root=r1.root,
        right_morphism_root=r2.root,
        composed_envelope_root=composed.root,
        midpoint_domain_root=b,
        interface_contract_root=h("INTERFACE", "B"),
        verifier_root=h("COMPVER", 1),
        policy_root=h("COMPPOL", 1),
    )
    comp_store.put(comp_proof)
    result, receipt = registry.compose_and_issue(
        r1,
        r2,
        composed,
        receipt_store=morph_store,
        composition_store=comp_store,
        composition_proof_root=comp_proof.root,
    )
    assert result.status == "PASS"
    assert receipt is not None
    assert receipt.predecessor_morphism_roots == tuple(sorted((r1.root, r2.root)))

    spliced = make_space("splice", h("D", "X"), c)
    result2, receipt2 = registry.compose_and_issue(
        r1,
        r2,
        spliced,
        receipt_store=morph_store,
        composition_store=comp_store,
        composition_proof_root=comp_proof.root,
    )
    assert result2.status == "FAIL_MORPHISM_DENIED"
    assert receipt2 is None
    assert "MORPHISM_COMPOSITION_OUTER_ENDPOINT_MISMATCH" in result2.error_codes
