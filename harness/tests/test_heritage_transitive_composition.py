from __future__ import annotations

import hashlib
import inspect
from dataclasses import fields

import pytest

from harness.sdk import heritage_composition as hc
from harness.sdk.meaning_heritage import (
    ClaimRef,
    ClaimSetEnvelopeV1,
    ClaimSetReceiptV1,
    ClaimSetVerifierV13,
    DeclaredAdditionEdge,
    DerivationProofReceiptV1,
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


TC_CODES = (
    "TRANSIENT_ADDITION_LEAK",
    "UNDECLARED_COMPOSITE_LOSS",
    "UNDECLARED_COMPOSITE_ADDITION",
    "COMPOSITION_PRESERVATION_UNPROVEN",
    "COMPOSITION_MIXED_ANCESTRY",
    "COMPOSITION_PARTITION_MISMATCH",
)


def h(domain: str, value: object) -> str:
    return canonical_hash(domain, value)


def claim(name: str) -> ClaimRef:
    return ClaimRef(name, h("TC_CLAIM", name), f"fp:{name}")


class FixedExtractor:
    def __init__(self, claims: tuple[ClaimRef, ...], salt: str) -> None:
        self.claims = claims
        self.extractor_root = h("TC_EXTRACTOR", salt)
        self.policy_root = h("TC_EXTRACTOR_POLICY", salt)

    def extract(self, payload: bytes) -> tuple[ClaimRef, ...]:
        return self.claims


class SemanticStore:
    def __init__(self) -> None:
        self.preservation: dict[str, PreservationProofReceiptV1] = {}
        self.derivation: dict[str, DerivationProofReceiptV1] = {}

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

    def put(self, receipt: HeritageReceiptV1) -> None:
        self.data[receipt.root] = receipt


class EnvelopeStore:
    def __init__(self) -> None:
        self.data: dict[str, SemanticLineageEnvelopeV1] = {}

    def fetch_verified(self, root: str):
        return self.data.get(root)

    def put(self, envelope: SemanticLineageEnvelopeV1) -> None:
        self.data[envelope.root] = envelope


class CompositionStore:
    def __init__(self) -> None:
        self.data: dict[str, hc.PreservationCompositionProofReceiptV1] = {}
        self.by_key: dict[tuple[str, str, str, str, str], hc.PreservationCompositionProofReceiptV1] = {}

    def fetch_verified(self, root: str):
        return self.data.get(root)

    def fetch_verified_for(
        self,
        *,
        left_proof_root: str,
        right_proof_root: str,
        source_claim_digest: str,
        midpoint_claim_digest: str,
        derived_claim_digest: str,
    ):
        return self.by_key.get(
            (
                left_proof_root,
                right_proof_root,
                source_claim_digest,
                midpoint_claim_digest,
                derived_claim_digest,
            )
        )

    def put(self, proof: hc.PreservationCompositionProofReceiptV1) -> None:
        self.data[proof.root] = proof
        self.by_key[
            (
                proof.left_proof_root,
                proof.right_proof_root,
                proof.source_claim_digest,
                proof.midpoint_claim_digest,
                proof.derived_claim_digest,
            )
        ] = proof


def issue_claimset(payload: bytes, claims: tuple[ClaimRef, ...], salt: str) -> ClaimSetReceiptV1:
    extractor = FixedExtractor(claims, salt)
    envelope = ClaimSetEnvelopeV1(
        lineage_id=f"claimset:{salt}",
        payload_root=hashlib.sha256(payload).hexdigest(),
        raw_claims=claims,
        extractor_root=extractor.extractor_root,
        extractor_policy_root=extractor.policy_root,
    )
    return ClaimSetVerifierV13.verify_and_issue(envelope, payload, extractor)


def preservation_edge(
    store: SemanticStore,
    source: ClaimRef,
    derived: ClaimRef,
    relation: PreservationRelation,
    salt: str,
) -> PreservationEdge:
    proof = PreservationProofReceiptV1(
        source_claim_digest=source.claim_digest,
        derived_claim_digest=derived.claim_digest,
        relation=relation,
        source_semantic_fingerprint=source.semantic_fingerprint,
        derived_semantic_fingerprint=derived.semantic_fingerprint,
        verifier_root=h("TC_PRESERVATION_VERIFIER", salt),
        policy_root=h("TC_PRESERVATION_POLICY", salt),
    )
    store.preservation[proof.root] = proof
    return PreservationEdge(source.claim_digest, derived.claim_digest, relation, proof.root)


def derivation_addition(
    store: SemanticStore,
    derived: ClaimRef,
    sources: tuple[ClaimRef, ...],
    transform_root: str,
    salt: str,
) -> DeclaredAdditionEdge:
    proof = DerivationProofReceiptV1(
        derived_claim_digest=derived.claim_digest,
        source_claim_digests=tuple(item.claim_digest for item in sources),
        source_semantic_fingerprints=tuple(item.semantic_fingerprint for item in sources),
        derived_semantic_fingerprint=derived.semantic_fingerprint,
        transform_root=transform_root,
        verifier_root=h("TC_DERIVATION_VERIFIER", salt),
        policy_root=h("TC_DERIVATION_POLICY", salt),
    )
    store.derivation[proof.root] = proof
    return DeclaredAdditionEdge(derived.claim_digest, proof.root)


def lineage(
    *,
    salt: str,
    source: ClaimSetReceiptV1,
    derived: ClaimSetReceiptV1,
    edges: tuple[PreservationEdge, ...],
    omissions: tuple[str, ...] = (),
    additions: tuple[DeclaredAdditionEdge, ...] = (),
    relation: TransformRelation = TransformRelation.LOSSLESS_TRANSFORM,
    loss_type: LossType = LossType.EXACT_LOSSLESS,
    uncertainty_bps: int = 0,
    transform_root: str | None = None,
) -> SemanticLineageEnvelopeV1:
    return SemanticLineageEnvelopeV1(
        lineage_id=f"lineage:{salt}",
        source_root=source.payload_root,
        source_claimset_receipt_root=source.root,
        derived_root=derived.payload_root,
        derived_claimset_receipt_root=derived.root,
        transform_root=transform_root or h("TC_TRANSFORM", salt),
        transform_relation=relation,
        loss_type=loss_type,
        preservation_edges=edges,
        declared_omission_digests=omissions,
        declared_additions=additions,
        uncertainty_bps=uncertainty_bps,
    )


def issue_heritage(
    envelope: SemanticLineageEnvelopeV1,
    source: ClaimSetReceiptV1,
    derived: ClaimSetReceiptV1,
    semantic_store: SemanticStore,
    claimset_store: ClaimSetStore,
    salt: str,
) -> HeritageReceiptV1:
    verifier = HeritageVerifierV13(
        verifier_root=h("TC_HERITAGE_VERIFIER", salt),
        policy_root=h("TC_HERITAGE_POLICY", salt),
        proof_store=semantic_store,
        claimset_store=claimset_store,
    )
    result, receipt = verifier.verify(envelope, source, derived)
    assert result.status == "PASS"
    assert receipt is not None
    return receipt


def kernel() -> hc.HeritageCompositionKernelV1:
    return hc.HeritageCompositionKernelV1(
        verifier_root=h("TC_COMPOSITION_VERIFIER", 1),
        policy_root=h("TC_COMPOSITION_POLICY", 1),
    )


@pytest.mark.parametrize("code", TC_CODES)
def test_tc_01_through_tc_06_are_preregistered_wire_codes(code: str) -> None:
    assert code in {item.value for item in hc.CompositionErrorCode}


def test_transitive_composition_trust_ports_and_receipts_exist() -> None:
    required = (
        "TrustedSemanticLineageEnvelopeStore",
        "TrustedPreservationCompositionProofStore",
        "PreservationCompositionProofReceiptV1",
        "HeritageCompositionReceiptV1",
        "HeritageCompositionKernelV1",
    )
    assert not tuple(name for name in required if not hasattr(hc, name))


def test_compose_surface_has_no_caller_authored_composed_state() -> None:
    params = inspect.signature(hc.HeritageCompositionKernelV1.compose).parameters
    forbidden = {"composed_envelope", "source_claimset", "derived_claimset"}
    assert not (forbidden & set(params))
    for required in (
        "heritage_store",
        "envelope_store",
        "claimset_store",
        "semantic_proof_store",
        "composition_proof_store",
    ):
        assert required in params


def test_composition_receipt_wire_authority_is_none() -> None:
    field_map = {item.name: item for item in fields(hc.HeritageCompositionReceiptV1)}
    assert field_map["authority_class"].default == "NONE"


def prepare_same_chain():
    a = claim("A")
    c1 = issue_claimset(b"c1", (a,), "c1")
    c2 = issue_claimset(b"c2", (a,), "c2")
    c3 = issue_claimset(b"c3", (a,), "c3")
    claims = ClaimSetStore(c1, c2, c3)
    semantic = SemanticStore()
    edge = preservation_edge(semantic, a, a, PreservationRelation.SAME_CLAIM_ROOT, "same")
    e1 = lineage(salt="e1", source=c1, derived=c2, edges=(edge,))
    e2 = lineage(salt="e2", source=c2, derived=c3, edges=(edge,))
    h1 = issue_heritage(e1, c1, c2, semantic, claims, "h1")
    h2 = issue_heritage(e2, c2, c3, semantic, claims, "h2")
    heritage = HeritageStore()
    heritage.put(h1)
    heritage.put(h2)
    envelopes = EnvelopeStore()
    envelopes.put(e1)
    envelopes.put(e2)
    return (a, c1, c2, c3, claims, semantic, heritage, envelopes, h1, h2)


def test_green_same_composition_is_mechanically_derived_and_partitioned() -> None:
    _, c1, _, c3, claims, semantic, heritage, envelopes, h1, h2 = prepare_same_chain()
    result, outcome = kernel().compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=CompositionStore(),
    )
    assert result.status == "PASS"
    assert outcome is not None
    assert outcome.composition_receipt.authority_class == "NONE"
    assert outcome.composition_receipt.mixed_ancestry_count == 0
    p13 = outcome.envelope.preservation_edges
    dom = {edge.source_claim_digest for edge in p13}
    ran = {edge.derived_claim_digest for edge in p13}
    o13 = set(outcome.envelope.declared_omission_digests)
    a13 = {edge.derived_claim_digest for edge in outcome.envelope.declared_additions}
    assert set(c1.claim_map) == dom | o13
    assert not (dom & o13)
    assert set(c3.claim_map) == ran | a13
    assert not (ran & a13)
    assert a13 == set()


def test_legacy_verifier_cannot_accept_caller_authored_composite_envelope() -> None:
    _, c1, _, c3, claims, semantic, heritage, envelopes, h1, h2 = prepare_same_chain()
    k = kernel()
    result, outcome = k.compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=CompositionStore(),
    )
    assert result.status == "PASS"
    assert outcome is not None

    legacy_verifier = HeritageVerifierV13(
        verifier_root=k.verifier_root,
        policy_root=k.policy_root,
        proof_store=semantic,
        claimset_store=claims,
    )
    with pytest.raises(AttributeError, match="compose"):
        legacy_verifier.compose(h1, h2, outcome.envelope, c1, c3)


def prepare_non_same_chain():
    a, b, c = claim("A"), claim("B"), claim("C")
    c1 = issue_claimset(b"ns1", (a,), "ns1")
    c2 = issue_claimset(b"ns2", (b,), "ns2")
    c3 = issue_claimset(b"ns3", (c,), "ns3")
    claims = ClaimSetStore(c1, c2, c3)
    semantic = SemanticStore()
    p1 = preservation_edge(semantic, a, b, PreservationRelation.SEMANTIC_EQUIVALENCE, "p1")
    p2 = preservation_edge(semantic, b, c, PreservationRelation.SEMANTIC_EQUIVALENCE, "p2")
    e1 = lineage(salt="ns-e1", source=c1, derived=c2, edges=(p1,))
    e2 = lineage(salt="ns-e2", source=c2, derived=c3, edges=(p2,))
    h1 = issue_heritage(e1, c1, c2, semantic, claims, "ns-h1")
    h2 = issue_heritage(e2, c2, c3, semantic, claims, "ns-h2")
    heritage = HeritageStore()
    heritage.put(h1)
    heritage.put(h2)
    envelopes = EnvelopeStore()
    envelopes.put(e1)
    envelopes.put(e2)
    return a, b, c, c1, c2, c3, claims, semantic, heritage, envelopes, h1, h2, p1, p2


def test_tc04_non_same_composition_requires_trusted_composition_proof() -> None:
    *_, claims, semantic, heritage, envelopes, h1, h2, _, _ = prepare_non_same_chain()
    result, outcome = kernel().compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=CompositionStore(),
    )
    assert outcome is None
    assert result.error_codes == ("COMPOSITION_PRESERVATION_UNPROVEN",)


def test_green_non_same_composition_requires_exact_fingerprint_bound_proof() -> None:
    a, b, c, _, _, _, claims, semantic, heritage, envelopes, h1, h2, p1, p2 = prepare_non_same_chain()
    store = CompositionStore()
    k = kernel()
    proof = hc.PreservationCompositionProofReceiptV1(
        left_proof_root=p1.proof_receipt_root,
        right_proof_root=p2.proof_receipt_root,
        source_claim_digest=a.claim_digest,
        midpoint_claim_digest=b.claim_digest,
        derived_claim_digest=c.claim_digest,
        source_semantic_fingerprint=a.semantic_fingerprint,
        midpoint_semantic_fingerprint=b.semantic_fingerprint,
        derived_semantic_fingerprint=c.semantic_fingerprint,
        relation=PreservationRelation.SEMANTIC_EQUIVALENCE,
        verifier_root=k.verifier_root,
        policy_root=k.policy_root,
    )
    store.put(proof)
    result, outcome = k.compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=store,
    )
    assert result.status == "PASS"
    assert outcome is not None
    assert outcome.envelope.preservation_edges[0].proof_receipt_root == proof.root


def prepare_first_step_addition(*, second_readds: bool = False, mixed: bool = False):
    a, t, z = claim("A"), claim("T"), claim("Z")
    c1 = issue_claimset(b"a1", (a,), "a1")
    c2 = issue_claimset(b"a2", (a, t), "a2")
    target_claims = (a, t) if second_readds else (a, z) if mixed else (a,)
    c3 = issue_claimset(b"a3", target_claims, "a3")
    claims = ClaimSetStore(c1, c2, c3)
    semantic = SemanticStore()
    same = preservation_edge(semantic, a, a, PreservationRelation.SAME_CLAIM_ROOT, "a-same")

    t1 = h("TC_TRANSFORM", "add-1")
    add_t = derivation_addition(semantic, t, (a,), t1, "add-t")
    e1 = lineage(
        salt="add-e1",
        source=c1,
        derived=c2,
        edges=(same,),
        additions=(add_t,),
        relation=TransformRelation.AUGMENTING_TRANSFORM,
        transform_root=t1,
    )

    t2 = h("TC_TRANSFORM", "add-2")
    additions2: tuple[DeclaredAdditionEdge, ...] = ()
    if second_readds:
        additions2 = (derivation_addition(semantic, t, (a,), t2, "readd-t"),)
    elif mixed:
        additions2 = (derivation_addition(semantic, z, (a, t), t2, "mixed-z"),)
    e2 = lineage(
        salt="add-e2",
        source=c2,
        derived=c3,
        edges=(same,),
        omissions=(t.claim_digest,),
        additions=additions2,
        relation=TransformRelation.LOSSY_TRANSFORM,
        loss_type=LossType.HEURISTIC_ABSTRACTION,
        uncertainty_bps=100,
        transform_root=t2,
    )
    h1 = issue_heritage(e1, c1, c2, semantic, claims, "add-h1")
    h2 = issue_heritage(e2, c2, c3, semantic, claims, "add-h2")
    heritage = HeritageStore()
    heritage.put(h1)
    heritage.put(h2)
    envelopes = EnvelopeStore()
    envelopes.put(e1)
    envelopes.put(e2)
    return claims, semantic, heritage, envelopes, h1, h2


def test_tc01_transient_addition_cannot_disappear_and_reappear_as_composite_state() -> None:
    claims, semantic, heritage, envelopes, h1, h2 = prepare_first_step_addition(second_readds=True)
    result, outcome = kernel().compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=CompositionStore(),
    )
    assert outcome is None
    assert result.error_codes == ("TRANSIENT_ADDITION_LEAK",)


def test_tc05_mixed_source_and_intermediate_addition_ancestry_fails_closed() -> None:
    claims, semantic, heritage, envelopes, h1, h2 = prepare_first_step_addition(mixed=True)
    result, outcome = kernel().compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=CompositionStore(),
    )
    assert outcome is None
    assert result.error_codes == ("COMPOSITION_MIXED_ANCESTRY",)


def test_tc03_final_addition_without_composed_derivation_proof_fails_closed() -> None:
    a, z = claim("A"), claim("Z")
    c1 = issue_claimset(b"u1", (a,), "u1")
    c2 = issue_claimset(b"u2", (a,), "u2")
    c3 = issue_claimset(b"u3", (a, z), "u3")
    claims = ClaimSetStore(c1, c2, c3)
    semantic = SemanticStore()
    same = preservation_edge(semantic, a, a, PreservationRelation.SAME_CLAIM_ROOT, "u-same")
    e1 = lineage(salt="u-e1", source=c1, derived=c2, edges=(same,))
    t2 = h("TC_TRANSFORM", "u-e2")
    add_z = derivation_addition(semantic, z, (a,), t2, "u-z")
    e2 = lineage(
        salt="u-e2",
        source=c2,
        derived=c3,
        edges=(same,),
        additions=(add_z,),
        relation=TransformRelation.AUGMENTING_TRANSFORM,
        transform_root=t2,
    )
    h1 = issue_heritage(e1, c1, c2, semantic, claims, "u-h1")
    h2 = issue_heritage(e2, c2, c3, semantic, claims, "u-h2")
    heritage = HeritageStore()
    heritage.put(h1)
    heritage.put(h2)
    envelopes = EnvelopeStore()
    envelopes.put(e1)
    envelopes.put(e2)

    result, outcome = kernel().compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=CompositionStore(),
    )
    assert outcome is None
    assert result.error_codes == ("UNDECLARED_COMPOSITE_ADDITION",)


def test_tc02_and_tc06_remain_explicit_internal_postcondition_guards() -> None:
    source = inspect.getsource(hc.HeritageCompositionKernelV1.compose)
    assert "UNDECLARED_COMPOSITE_LOSS" in source
    assert "COMPOSITION_PARTITION_MISMATCH" in source
    assert "source_digests != dom | o13" in source
    assert "target_digests != ran | a13" in source
