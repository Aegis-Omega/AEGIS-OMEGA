from __future__ import annotations

import runpy
from dataclasses import fields, replace

import pytest

from harness.sdk import heritage_composition as hc
from harness.sdk.meaning_heritage import PreservationRelation


PARENT = runpy.run_path("harness/tests/test_heritage_transitive_composition.py")
h = PARENT["h"]
claim = PARENT["claim"]
issue_claimset = PARENT["issue_claimset"]
ClaimSetStore = PARENT["ClaimSetStore"]
SemanticStore = PARENT["SemanticStore"]
HeritageStore = PARENT["HeritageStore"]
EnvelopeStore = PARENT["EnvelopeStore"]
CompositionStore = PARENT["CompositionStore"]
preservation_edge = PARENT["preservation_edge"]
derivation_addition = PARENT["derivation_addition"]
lineage = PARENT["lineage"]
issue_heritage = PARENT["issue_heritage"]
kernel = PARENT["kernel"]
TransformRelation = PARENT["TransformRelation"]


class DerivationCompositionStore(CompositionStore):
    def __init__(self) -> None:
        super().__init__()
        self.derivation = {}
        self.derivation_by_key = {}

    def fetch_derivation_verified(self, root: str):
        return self.derivation.get(root)

    def fetch_derivation_verified_for(
        self,
        *,
        right_derivation_proof_root: str,
        derived_claim_digest: str,
        composed_transform_root: str,
    ):
        return self.derivation_by_key.get(
            (
                right_derivation_proof_root,
                derived_claim_digest,
                composed_transform_root,
            )
        )

    def put_derivation(self, proof) -> None:
        self.derivation[proof.root] = proof
        self.derivation_by_key[
            (
                proof.right_derivation_proof_root,
                proof.derived_claim_digest,
                proof.transform_root,
            )
        ] = proof


def prepare_source_ancestry_final_addition():
    a = claim("DA-A")
    z = claim("DA-Z")
    c1 = issue_claimset(b"da-c1", (a,), "da-c1")
    c2 = issue_claimset(b"da-c2", (a,), "da-c2")
    c3 = issue_claimset(b"da-c3", (a, z), "da-c3")
    claims = ClaimSetStore(c1, c2, c3)
    semantic = SemanticStore()

    same = preservation_edge(
        semantic,
        a,
        a,
        PreservationRelation.SAME_CLAIM_ROOT,
        "da-same",
    )
    e1 = lineage(salt="da-e1", source=c1, derived=c2, edges=(same,))

    t2 = h("TC_TRANSFORM", "da-e2")
    add_z = derivation_addition(semantic, z, (a,), t2, "da-z")
    e2 = lineage(
        salt="da-e2",
        source=c2,
        derived=c3,
        edges=(same,),
        additions=(add_z,),
        relation=TransformRelation.AUGMENTING_TRANSFORM,
        transform_root=t2,
    )

    h1 = issue_heritage(e1, c1, c2, semantic, claims, "da-h1")
    h2 = issue_heritage(e2, c2, c3, semantic, claims, "da-h2")
    heritage = HeritageStore()
    heritage.put(h1)
    heritage.put(h2)
    envelopes = EnvelopeStore()
    envelopes.put(e1)
    envelopes.put(e2)
    right_derivation = semantic.derivation[add_z.derivation_receipt_root]
    return (
        a,
        z,
        c1,
        c2,
        c3,
        claims,
        semantic,
        heritage,
        envelopes,
        h1,
        h2,
        e1,
        e2,
        same,
        right_derivation,
    )


def composed_transform_root(k, e1, e2):
    return h(
        hc.DOM_TRANSITIVE_TRANSFORM,
        {
            "left_envelope_root": e1.root,
            "right_envelope_root": e2.root,
            "left_transform_root": e1.transform_root,
            "right_transform_root": e2.transform_root,
            "composition_verifier_root": k.verifier_root,
            "composition_policy_root": k.policy_root,
        },
    )


def test_derivation_composition_types_are_preregistered() -> None:
    required = (
        "DerivationSourceLineageBindingV1",
        "DerivationCompositionProofReceiptV1",
        "TrustedDerivationCompositionProofStore",
        "TrustedHeritageCompositionProofStore",
    )
    missing = tuple(name for name in required if not hasattr(hc, name))
    assert not missing, f"DERIVATION_COMPOSITION_RUNTIME_NOT_IMPLEMENTED:{missing}"


def test_derivation_composition_receipt_wire_authority_is_none() -> None:
    proof_type = getattr(hc, "DerivationCompositionProofReceiptV1", None)
    assert proof_type is not None, "DERIVATION_COMPOSITION_PROOF_NOT_IMPLEMENTED"
    field_map = {item.name: item for item in fields(proof_type)}
    assert field_map["authority_class"].default == "NONE"


def test_final_addition_without_composition_proof_remains_fail_closed() -> None:
    (
        _,
        _,
        _,
        _,
        _,
        claims,
        semantic,
        heritage,
        envelopes,
        h1,
        h2,
        *_rest,
    ) = prepare_source_ancestry_final_addition()
    result, outcome = kernel().compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=DerivationCompositionStore(),
    )
    assert outcome is None
    assert result.error_codes == ("UNDECLARED_COMPOSITE_ADDITION",)


def test_source_ancestry_final_addition_with_exact_composition_proof_is_green() -> None:
    (
        a,
        z,
        _,
        _,
        _,
        claims,
        semantic,
        heritage,
        envelopes,
        h1,
        h2,
        e1,
        e2,
        same,
        right_derivation,
    ) = prepare_source_ancestry_final_addition()
    k = kernel()
    proof_type = getattr(hc, "DerivationCompositionProofReceiptV1", None)
    binding_type = getattr(hc, "DerivationSourceLineageBindingV1", None)
    assert proof_type is not None and binding_type is not None
    transform_root = composed_transform_root(k, e1, e2)
    binding = binding_type(
        source_claim_digest=a.claim_digest,
        midpoint_claim_digest=a.claim_digest,
        source_semantic_fingerprint=a.semantic_fingerprint,
        midpoint_semantic_fingerprint=a.semantic_fingerprint,
        preservation_proof_root=same.proof_receipt_root,
    )
    proof = proof_type(
        right_derivation_proof_root=right_derivation.root,
        source_bindings=(binding,),
        derived_claim_digest=z.claim_digest,
        derived_semantic_fingerprint=z.semantic_fingerprint,
        left_envelope_root=e1.root,
        right_envelope_root=e2.root,
        left_transform_root=e1.transform_root,
        right_transform_root=e2.transform_root,
        transform_root=transform_root,
        verifier_root=k.verifier_root,
        policy_root=k.policy_root,
    )
    store = DerivationCompositionStore()
    store.put_derivation(proof)
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
    assert outcome.composition_receipt.authority_class == "NONE"
    additions = outcome.envelope.declared_additions
    assert len(additions) == 1
    assert additions[0].derived_claim_digest == z.claim_digest
    assert additions[0].derivation_receipt_root == proof.root


def test_fingerprint_spliced_derivation_composition_proof_is_rejected() -> None:
    (
        a,
        z,
        _,
        _,
        _,
        claims,
        semantic,
        heritage,
        envelopes,
        h1,
        h2,
        e1,
        e2,
        same,
        right_derivation,
    ) = prepare_source_ancestry_final_addition()
    k = kernel()
    proof_type = getattr(hc, "DerivationCompositionProofReceiptV1", None)
    binding_type = getattr(hc, "DerivationSourceLineageBindingV1", None)
    assert proof_type is not None and binding_type is not None
    transform_root = composed_transform_root(k, e1, e2)
    forged_binding = binding_type(
        source_claim_digest=a.claim_digest,
        midpoint_claim_digest=a.claim_digest,
        source_semantic_fingerprint="fp:forged-source",
        midpoint_semantic_fingerprint=a.semantic_fingerprint,
        preservation_proof_root=same.proof_receipt_root,
    )
    forged = proof_type(
        right_derivation_proof_root=right_derivation.root,
        source_bindings=(forged_binding,),
        derived_claim_digest=z.claim_digest,
        derived_semantic_fingerprint=z.semantic_fingerprint,
        left_envelope_root=e1.root,
        right_envelope_root=e2.root,
        left_transform_root=e1.transform_root,
        right_transform_root=e2.transform_root,
        transform_root=transform_root,
        verifier_root=k.verifier_root,
        policy_root=k.policy_root,
    )
    store = DerivationCompositionStore()
    store.put_derivation(forged)
    result, outcome = k.compose(
        h1,
        h2,
        heritage_store=heritage,
        envelope_store=envelopes,
        claimset_store=claims,
        semantic_proof_store=semantic,
        composition_proof_store=store,
    )
    assert outcome is None
    assert result.error_codes == ("UNDECLARED_COMPOSITE_ADDITION",)


def test_composition_proof_root_binds_predecessor_and_fingerprint_context() -> None:
    proof_type = getattr(hc, "DerivationCompositionProofReceiptV1", None)
    binding_type = getattr(hc, "DerivationSourceLineageBindingV1", None)
    assert proof_type is not None and binding_type is not None
    binding = binding_type(
        source_claim_digest=h("SRC", 1),
        midpoint_claim_digest=h("MID", 1),
        source_semantic_fingerprint="fp:src",
        midpoint_semantic_fingerprint="fp:mid",
        preservation_proof_root=h("PRES", 1),
    )
    kwargs = dict(
        right_derivation_proof_root=h("DER", 1),
        source_bindings=(binding,),
        derived_claim_digest=h("DST", 1),
        derived_semantic_fingerprint="fp:dst",
        left_envelope_root=h("ENV", 1),
        right_envelope_root=h("ENV", 2),
        left_transform_root=h("TRANS", 1),
        right_transform_root=h("TRANS", 2),
        transform_root=h("TRANS", 3),
        verifier_root=h("VER", 1),
        policy_root=h("POL", 1),
    )
    proof = proof_type(**kwargs)
    forged = proof_type(
        **{**kwargs, "derived_semantic_fingerprint": "fp:dst-forged"}
    )
    assert proof.root != forged.root
    assert proof.authority_class == "NONE"
