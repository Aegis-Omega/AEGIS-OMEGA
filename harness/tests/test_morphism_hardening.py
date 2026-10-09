from __future__ import annotations

from dataclasses import asdict

from harness.sdk.meaning_heritage import HeritageReceiptV1, canonical_hash
from harness.sdk.morphisms import (
    CarrierProofObligationV1,
    CarrierVerifierV1,
    CompositionProofReceiptV1,
    HeritageMorphismVerifierV1,
    LimitVerifierV1,
    MorphismEnvelopeV1,
    MorphismKind,
    MorphismVerifierRegistryV1,
    ProofArtifactKind,
    ProofArtifactReceiptV1,
    RepresentationProofObligationV1,
    RepresentationVerifierV1,
    SemanticVerifierV1,
    SpaceProofObligationV1,
    SpaceVerifierV1,
    TheoremContextV1,
)


def h(domain: str, value: object) -> str:
    return canonical_hash(domain, value)


class ProofStore:
    def __init__(self) -> None:
        self.data: dict[str, ProofArtifactReceiptV1] = {}

    def put(self, receipt: ProofArtifactReceiptV1) -> str:
        self.data[receipt.root] = receipt
        return receipt.root

    def fetch_verified(self, root: str):
        return self.data.get(root)


class HeritageStore:
    def __init__(self) -> None:
        self.data: dict[str, HeritageReceiptV1] = {}

    def fetch_verified(self, root: str):
        return self.data.get(root)


class MorphismStore:
    def __init__(self) -> None:
        self.data = {}

    def put(self, receipt):
        self.data[receipt.root] = receipt
        return receipt.root

    def fetch_verified(self, root: str):
        return self.data.get(root)


class CompositionStore:
    def __init__(self) -> None:
        self.data: dict[str, CompositionProofReceiptV1] = {}

    def put(self, receipt: CompositionProofReceiptV1) -> str:
        self.data[receipt.root] = receipt
        return receipt.root

    def fetch_verified(self, root: str):
        return self.data.get(root)


def proof_receipt(kind: ProofArtifactKind, subject_root: str, salt: str) -> ProofArtifactReceiptV1:
    return ProofArtifactReceiptV1(
        proof_kind=kind,
        subject_root=subject_root,
        verifier_root=h("TEST_PROOF_VERIFIER", salt),
        policy_root=h("TEST_PROOF_POLICY", salt),
        status="PASS",
        proof_context_root=h("TEST_PROOF_CONTEXT", salt),
    )


def registry(proof_store: ProofStore, heritage_store: HeritageStore):
    common = dict(
        verifier_root=h("MORPHISM_VERIFIER", 1),
        policy_root=h("MORPHISM_POLICY", 1),
        proof_store=proof_store,
    )
    return MorphismVerifierRegistryV1((
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
    ))


def test_carrier_proof_cannot_be_spliced_to_different_envelope_endpoints():
    proof_store = ProofStore()
    source = TheoremContextV1(h("T", 1), h("CARRIER", "A"), h("H", 1), h("N", 1), h("CTX", 1))
    target = TheoremContextV1(h("T", 2), h("CARRIER", "B"), h("H", 2), h("N", 2), h("CTX", 2))
    transport_map = h("MAP", "A->B")
    subject = h(
        "AEGIS_CARRIER_TRANSPORT_SUBJECT_V1",
        {"source": asdict(source), "target": asdict(target), "transport_map_root": transport_map},
    )
    transport = proof_receipt(ProofArtifactKind.CARRIER_TRANSPORT, subject, "carrier")
    proof_store.put(transport)

    verifier = CarrierVerifierV1(
        verifier_root=h("MV", "carrier"),
        policy_root=h("MP", "carrier"),
        proof_store=proof_store,
    )
    spliced = MorphismEnvelopeV1(
        morphism_id="carrier-spliced",
        kind=MorphismKind.CARRIER,
        source_domain_root=h("CARRIER", "X"),
        target_domain_root=target.carrier_root,
        proof_obligation=CarrierProofObligationV1(source, target, transport_map, transport.root),
    )
    assert "CARRIER_ENDPOINT_BINDING_FAILURE" in verifier.verify(spliced)


def test_one_proof_kind_cannot_satisfy_three_representation_obligations():
    proof_store = ProofStore()
    source = h("REP", "A")
    target = h("REP", "B")
    forward = h("MAP", "f")
    inverse = h("MAP", "g")
    subject = h(
        "AEGIS_REPRESENTATION_ISOMORPHISM_SUBJECT_V1",
        {"source": source, "target": target, "forward": forward, "inverse": inverse},
    )
    left_only = proof_receipt(ProofArtifactKind.REPRESENTATION_LEFT_INVERSE, subject, "left")
    proof_store.put(left_only)
    env = MorphismEnvelopeV1(
        morphism_id="rep-reuse",
        kind=MorphismKind.REPRESENTATION,
        source_domain_root=source,
        target_domain_root=target,
        proof_obligation=RepresentationProofObligationV1(
            source_representation_root=source,
            target_representation_root=target,
            forward_map_root=forward,
            inverse_map_root=inverse,
            left_inverse_proof_root=left_only.root,
            right_inverse_proof_root=left_only.root,
            observable_commutation_proof_root=left_only.root,
        ),
    )
    verifier = RepresentationVerifierV1(
        verifier_root=h("MV", "rep"),
        policy_root=h("MP", "rep"),
        proof_store=proof_store,
    )
    errors = verifier.verify(env)
    assert "REPRESENTATION_RIGHT_INVERSE_INVALID" in errors
    assert "REPRESENTATION_COMMUTATION_INVALID" in errors


def make_space(proof_store: ProofStore, name: str, src: str, dst: str) -> MorphismEnvelopeV1:
    subject_root = h("SUBJECT", name)
    proof_subject = h(
        "AEGIS_SPACE_SUBJECT_V1",
        {"subject_root": subject_root, "source_space_root": src, "target_space_root": dst},
    )
    image = proof_receipt(ProofArtifactKind.SPACE_IMAGE_MEMBERSHIP, proof_subject, name + "-image")
    admissible = proof_receipt(ProofArtifactKind.SPACE_ADMISSIBILITY, proof_subject, name + "-admissible")
    proof_store.put(image)
    proof_store.put(admissible)
    return MorphismEnvelopeV1(
        morphism_id=f"space-{name}",
        kind=MorphismKind.SPACE,
        source_domain_root=src,
        target_domain_root=dst,
        proof_obligation=SpaceProofObligationV1(
            subject_root=subject_root,
            source_space_root=src,
            target_space_root=dst,
            image_membership_receipt_root=image.root,
            admissibility_receipt_root=admissible.root,
        ),
    )


def test_composition_requires_authenticated_composition_proof():
    proof_store = ProofStore()
    heritage_store = HeritageStore()
    morphism_store = MorphismStore()
    composition_store = CompositionStore()
    reg = registry(proof_store, heritage_store)

    a, b, c = h("DOMAIN", "A"), h("DOMAIN", "B"), h("DOMAIN", "C")
    e1 = make_space(proof_store, "one", a, b)
    e2 = make_space(proof_store, "two", b, c)
    _, r1 = reg.verify_and_issue(e1)
    _, r2 = reg.verify_and_issue(e2)
    assert r1 is not None and r2 is not None
    morphism_store.put(r1)
    morphism_store.put(r2)

    composed = make_space(proof_store, "composed", a, c)
    fake_composition_root = h("FAKE_COMPOSITION_PROOF", 1)
    result, receipt = reg.compose_and_issue(
        r1,
        r2,
        composed,
        receipt_store=morphism_store,
        composition_store=composition_store,
        composition_proof_root=fake_composition_root,
    )
    assert receipt is None
    assert "MORPHISM_COMPOSITION_PROOF_UNTRUSTED" in result.error_codes

    proof = CompositionProofReceiptV1(
        left_morphism_root=r1.root,
        right_morphism_root=r2.root,
        composed_envelope_root=composed.root,
        midpoint_domain_root=b,
        interface_contract_root=h("INTERFACE", "B"),
        verifier_root=h("COMPOSITION_VERIFIER", 1),
        policy_root=h("COMPOSITION_POLICY", 1),
        status="PASS",
    )
    composition_store.put(proof)
    result2, receipt2 = reg.compose_and_issue(
        r1,
        r2,
        composed,
        receipt_store=morphism_store,
        composition_store=composition_store,
        composition_proof_root=proof.root,
    )
    assert result2.status == "PASS"
    assert receipt2 is not None
    assert receipt2.verification_root != r1.verification_root
    assert receipt2.verification_root != r2.verification_root
