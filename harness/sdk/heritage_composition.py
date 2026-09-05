"""AEGIS MHP-1 derivation-aware semantic-lineage composition kernel v1.

The pre-existing transitive composition kernel is frozen byte-for-byte in
``heritage_composition_base.py``.  This module extends that verified surface with
one deliberately narrow GREEN path: a final claim introduced by the right
predecessor may survive composition only when its right-step derivation receipt
is trusted and every derivation source is transported from C1 to C2 through an
authenticated preservation edge bound into a trusted derivation-composition
proof.

This module is evidence-only.  It never grants execution, admission, theorem, or
canonical-control authority.  Every proof/receipt introduced here has wire
authority ``NONE``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol

from harness.sdk import heritage_composition_base as _base
from harness.sdk.heritage_composition_base import *  # noqa: F401,F403
from harness.sdk.meaning_heritage import DeclaredAdditionEdge

DOM_DERIVATION_COMPOSITION_PROOF = "AEGIS_MHP1_DERIVATION_COMPOSITION_PROOF_V1"


@dataclass(frozen=True)
class DerivationSourceLineageBindingV1:
    """One authenticated C1 -> C2 source path used by a composed derivation."""

    source_claim_digest: str
    midpoint_claim_digest: str
    source_semantic_fingerprint: str
    midpoint_semantic_fingerprint: str
    preservation_proof_root: str

    def __post_init__(self) -> None:
        _base.require_hash("source_claim_digest", self.source_claim_digest)
        _base.require_hash("midpoint_claim_digest", self.midpoint_claim_digest)
        _base.require_hash("preservation_proof_root", self.preservation_proof_root)
        _base.require_id("source_semantic_fingerprint", self.source_semantic_fingerprint)
        _base.require_id("midpoint_semantic_fingerprint", self.midpoint_semantic_fingerprint)


@dataclass(frozen=True)
class DerivationCompositionProofReceiptV1:
    """Proof-carrying transitive derivation bound to both predecessor steps."""

    right_derivation_proof_root: str
    source_bindings: tuple[DerivationSourceLineageBindingV1, ...]
    derived_claim_digest: str
    derived_semantic_fingerprint: str
    left_envelope_root: str
    right_envelope_root: str
    left_transform_root: str
    right_transform_root: str
    transform_root: str
    verifier_root: str
    policy_root: str
    status: str = _base.PASS
    authority_class: str = field(default=_base.NO_AUTHORITY, init=False)
    schema_version: str = "aegis.derivation-composition-proof-receipt.v1"

    def __post_init__(self) -> None:
        for name in (
            "right_derivation_proof_root",
            "derived_claim_digest",
            "left_envelope_root",
            "right_envelope_root",
            "left_transform_root",
            "right_transform_root",
            "transform_root",
            "verifier_root",
            "policy_root",
        ):
            _base.require_hash(name, getattr(self, name))
        _base.require_id("derived_semantic_fingerprint", self.derived_semantic_fingerprint)
        if not self.source_bindings:
            raise ValueError("DERIVATION_COMPOSITION_SOURCE_BINDINGS_EMPTY")
        source_keys = tuple(item.source_claim_digest for item in self.source_bindings)
        midpoint_keys = tuple(item.midpoint_claim_digest for item in self.source_bindings)
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("DERIVATION_COMPOSITION_SOURCE_DUPLICATE")
        if len(midpoint_keys) != len(set(midpoint_keys)):
            raise ValueError("DERIVATION_COMPOSITION_MIDPOINT_DUPLICATE")
        if self.status != _base.PASS:
            raise ValueError("DERIVATION_COMPOSITION_PROOF_NOT_PASS")

    @property
    def source_claim_digests(self) -> tuple[str, ...]:
        return tuple(item.source_claim_digest for item in self.source_bindings)

    @property
    def source_semantic_fingerprints(self) -> tuple[str, ...]:
        return tuple(item.source_semantic_fingerprint for item in self.source_bindings)

    @property
    def root(self) -> str:
        payload = asdict(self)
        payload["source_bindings"] = [asdict(item) for item in self.source_bindings]
        return _base.canonical_hash(DOM_DERIVATION_COMPOSITION_PROOF, payload)


class TrustedDerivationCompositionProofStore(Protocol):
    def fetch_derivation_verified(
        self, root: str
    ) -> DerivationCompositionProofReceiptV1 | None: ...

    def fetch_derivation_verified_for(
        self,
        *,
        right_derivation_proof_root: str,
        derived_claim_digest: str,
        composed_transform_root: str,
    ) -> DerivationCompositionProofReceiptV1 | None: ...


class TrustedHeritageCompositionProofStore(
    TrustedPreservationCompositionProofStore,
    TrustedDerivationCompositionProofStore,
    Protocol,
):
    """Combined trusted store port for preservation and derivation composition."""


class _CompositionAndDerivationProofStore:
    def __init__(
        self,
        semantic_store: _base.TrustedSemanticProofStore,
        composition_store: TrustedHeritageCompositionProofStore,
    ) -> None:
        self.semantic_store = semantic_store
        self.composition_store = composition_store

    def fetch_preservation(self, root: str):
        proof = self.semantic_store.fetch_preservation(root)
        if proof is not None:
            return proof
        return self.composition_store.fetch_verified(root)

    def fetch_derivation(self, root: str):
        proof = self.semantic_store.fetch_derivation(root)
        if proof is not None:
            return proof
        fetch = getattr(self.composition_store, "fetch_derivation_verified", None)
        if fetch is None:
            return None
        return fetch(root)


class HeritageCompositionKernelV1(_base.HeritageCompositionKernelV1):
    """Base transitive kernel plus source-only final-addition derivation closure."""

    def _validate_derivation_composition_proof(
        self,
        *,
        proof: DerivationCompositionProofReceiptV1,
        right_derivation,
        derived_claim_digest: str,
        e1,
        e2,
        c1,
        c2,
        c3,
        semantic_proof_store,
        composed_transform_root: str,
    ) -> bool:
        derived_claim = c3.claim_map.get(derived_claim_digest)
        if derived_claim is None:
            return False
        if (
            proof.right_derivation_proof_root != right_derivation.root
            or proof.derived_claim_digest != derived_claim_digest
            or proof.derived_semantic_fingerprint != derived_claim.semantic_fingerprint
            or proof.left_envelope_root != e1.root
            or proof.right_envelope_root != e2.root
            or proof.left_transform_root != e1.transform_root
            or proof.right_transform_root != e2.transform_root
            or proof.transform_root != composed_transform_root
            or proof.verifier_root != self.verifier_root
            or proof.policy_root != self.policy_root
            or right_derivation.derived_claim_digest != derived_claim_digest
            or right_derivation.derived_semantic_fingerprint
            != derived_claim.semantic_fingerprint
            or right_derivation.transform_root != e2.transform_root
            or len(proof.source_bindings) != len(right_derivation.source_claim_digests)
        ):
            return False

        authenticated_midpoint_fingerprints: list[str] = []
        for midpoint_digest in right_derivation.source_claim_digests:
            midpoint_claim = c2.claim_map.get(midpoint_digest)
            if midpoint_claim is None:
                return False
            authenticated_midpoint_fingerprints.append(midpoint_claim.semantic_fingerprint)
        if tuple(authenticated_midpoint_fingerprints) != tuple(
            right_derivation.source_semantic_fingerprints
        ):
            return False

        for binding, midpoint_digest in zip(
            proof.source_bindings, right_derivation.source_claim_digests
        ):
            if binding.midpoint_claim_digest != midpoint_digest:
                return False
            source_claim = c1.claim_map.get(binding.source_claim_digest)
            midpoint_claim = c2.claim_map.get(binding.midpoint_claim_digest)
            if source_claim is None or midpoint_claim is None:
                return False
            if (
                binding.source_semantic_fingerprint != source_claim.semantic_fingerprint
                or binding.midpoint_semantic_fingerprint
                != midpoint_claim.semantic_fingerprint
            ):
                return False

            matching_edges = tuple(
                edge
                for edge in e1.preservation_edges
                if edge.source_claim_digest == binding.source_claim_digest
                and edge.derived_claim_digest == binding.midpoint_claim_digest
                and edge.proof_receipt_root == binding.preservation_proof_root
            )
            if len(matching_edges) != 1:
                return False
            if (
                self._edge_proof(
                    matching_edges[0], c1, c2, semantic_proof_store
                )
                is None
            ):
                return False

        return True

    def _compose_source_only_final_additions(
        self,
        original_result,
        h1,
        h2,
        *,
        heritage_store,
        envelope_store,
        claimset_store,
        semantic_proof_store,
        composition_proof_store,
    ):
        e1 = self._trusted_envelope(envelope_store, h1.envelope_root)
        e2 = self._trusted_envelope(envelope_store, h2.envelope_root)
        c1 = self._trusted_claimset(claimset_store, h1.source_claimset_receipt_root)
        c2 = self._trusted_claimset(claimset_store, h1.derived_claimset_receipt_root)
        c3 = self._trusted_claimset(claimset_store, h2.derived_claimset_receipt_root)
        if e1 is None or e2 is None or c1 is None or c2 is None or c3 is None:
            return original_result, None

        right_by_source: dict[str, list[_base.PreservationEdge]] = {}
        for edge in e2.preservation_edges:
            right_by_source.setdefault(edge.source_claim_digest, []).append(edge)

        composed: list[_base.PreservationEdge] = []
        seen_pair_rel: dict[tuple[str, str], _base.PreservationRelation] = {}
        for left_edge in e1.preservation_edges:
            left_proof = self._edge_proof(left_edge, c1, c2, semantic_proof_store)
            if left_proof is None:
                return original_result, None
            for right_edge in right_by_source.get(left_edge.derived_claim_digest, []):
                right_proof = self._edge_proof(right_edge, c2, c3, semantic_proof_store)
                if right_proof is None:
                    return original_result, None
                composed_relation = self._compose_relation(
                    left_edge=left_edge,
                    right_edge=right_edge,
                    left_proof=left_proof,
                    right_proof=right_proof,
                    c1=c1,
                    c2=c2,
                    c3=c3,
                    composition_store=composition_proof_store,
                )
                if composed_relation is None:
                    return original_result, None
                relation, proof_root = composed_relation
                pair = (left_edge.source_claim_digest, right_edge.derived_claim_digest)
                prior = seen_pair_rel.get(pair)
                if prior is not None and prior != relation:
                    return original_result, None
                seen_pair_rel[pair] = relation
                edge = _base.PreservationEdge(pair[0], pair[1], relation, proof_root)
                if edge not in composed:
                    composed.append(edge)

        composed_edges = tuple(
            sorted(
                composed,
                key=lambda edge: (
                    edge.source_claim_digest,
                    edge.derived_claim_digest,
                    edge.relation.value,
                ),
            )
        )
        dom = {edge.source_claim_digest for edge in composed_edges}
        ran = {edge.derived_claim_digest for edge in composed_edges}
        source_digests = set(c1.claim_map)
        target_digests = set(c3.claim_map)
        o13 = source_digests - dom
        a13 = target_digests - ran

        # V1 deliberately declines mixed augmenting+lossy composition.  The only
        # new GREEN surface is a source-only final addition over a lossless base.
        if not a13 or o13:
            return original_result, None

        o1 = set(e1.declared_omission_digests)
        o2 = set(e2.declared_omission_digests)
        a1 = {item.derived_claim_digest for item in e1.declared_additions}
        transient = a1 & o2
        inherited_loss = {
            edge.source_claim_digest
            for edge in e1.preservation_edges
            if edge.derived_claim_digest in o2
        }
        mixed = self._mixed_ancestry(e1, e2, semantic_proof_store)
        if transient & target_digests or mixed or o13 != o1 | inherited_loss:
            return original_result, None

        transform_root = _base.canonical_hash(
            _base.DOM_TRANSITIVE_TRANSFORM,
            {
                "left_envelope_root": e1.root,
                "right_envelope_root": e2.root,
                "left_transform_root": e1.transform_root,
                "right_transform_root": e2.transform_root,
                "composition_verifier_root": self.verifier_root,
                "composition_policy_root": self.policy_root,
            },
        )

        fetch_for = getattr(
            composition_proof_store, "fetch_derivation_verified_for", None
        )
        fetch_root = getattr(
            composition_proof_store, "fetch_derivation_verified", None
        )
        if fetch_for is None or fetch_root is None:
            return original_result, None

        right_additions = {
            item.derived_claim_digest: item for item in e2.declared_additions
        }
        declared_additions: list[DeclaredAdditionEdge] = []
        for digest in sorted(a13):
            right_addition = right_additions.get(digest)
            if right_addition is None:
                return original_result, None
            right_derivation = semantic_proof_store.fetch_derivation(
                right_addition.derivation_receipt_root
            )
            if (
                right_derivation is None
                or right_derivation.root != right_addition.derivation_receipt_root
            ):
                return original_result, None

            proof = fetch_for(
                right_derivation_proof_root=right_derivation.root,
                derived_claim_digest=digest,
                composed_transform_root=transform_root,
            )
            if proof is None or fetch_root(proof.root) != proof:
                return original_result, None
            if not self._validate_derivation_composition_proof(
                proof=proof,
                right_derivation=right_derivation,
                derived_claim_digest=digest,
                e1=e1,
                e2=e2,
                c1=c1,
                c2=c2,
                c3=c3,
                semantic_proof_store=semantic_proof_store,
                composed_transform_root=transform_root,
            ):
                return original_result, None
            declared_additions.append(DeclaredAdditionEdge(digest, proof.root))

        lineage_id = _base.canonical_hash(
            "AEGIS_MHP1_TRANSITIVE_LINEAGE_ID_V1",
            {"left": e1.root, "right": e2.root, "transform_root": transform_root},
        )
        envelope = _base.SemanticLineageEnvelopeV1(
            lineage_id=lineage_id,
            source_root=c1.payload_root,
            source_claimset_receipt_root=c1.root,
            derived_root=c3.payload_root,
            derived_claimset_receipt_root=c3.root,
            transform_root=transform_root,
            transform_relation=_base.TransformRelation.AUGMENTING_TRANSFORM,
            loss_type=_base.LossType.EXACT_LOSSLESS,
            preservation_edges=composed_edges,
            declared_omission_digests=(),
            declared_additions=tuple(declared_additions),
            uncertainty_bps=0,
        )

        overlay = _CompositionAndDerivationProofStore(
            semantic_proof_store, composition_proof_store
        )
        verifier = _base.HeritageVerifierV13(
            verifier_root=self.verifier_root,
            policy_root=self.policy_root,
            proof_store=overlay,
            claimset_store=claimset_store,
            heritage_store=heritage_store,
        )
        result, heritage_receipt = verifier.verify(envelope, c1, c3, (h1, h2))
        if heritage_receipt is None or result.status != _base.PASS:
            return result, None

        composition_receipt = _base.HeritageCompositionReceiptV1(
            left_heritage_receipt_root=h1.root,
            right_heritage_receipt_root=h2.root,
            midpoint_claimset_receipt_root=c2.root,
            composed_source_claimset_receipt_root=c1.root,
            composed_target_claimset_receipt_root=c3.root,
            composed_envelope_root=envelope.root,
            composed_heritage_receipt_root=heritage_receipt.root,
            composed_preservation_root=_base._preservation_root(composed_edges),
            composed_omissions_root=_base._set_root(
                _base.DOM_COMPOSED_OMISSION_SET, o13
            ),
            composed_additions_root=_base._set_root(
                _base.DOM_COMPOSED_ADDITION_SET, a13
            ),
            transient_eliminated_root=_base._set_root(
                _base.DOM_TRANSIENT_ELIMINATED_SET, transient
            ),
            intermediate_inherited_loss_root=_base._set_root(
                _base.DOM_INTERMEDIATE_INHERITED_LOSS_SET, inherited_loss
            ),
            mixed_ancestry_root=_base._set_root(
                _base.DOM_MIXED_ANCESTRY_SET, mixed
            ),
            mixed_ancestry_count=len(mixed),
            composition_verifier_root=self.verifier_root,
            composition_policy_root=self.policy_root,
        )
        return result, _base.HeritageCompositionOutcomeV1(
            envelope=envelope,
            heritage_receipt=heritage_receipt,
            composition_receipt=composition_receipt,
        )

    def compose(
        self,
        h1,
        h2,
        *,
        heritage_store,
        envelope_store,
        claimset_store,
        semantic_proof_store,
        composition_proof_store,
    ):
        result, outcome = super().compose(
            h1,
            h2,
            heritage_store=heritage_store,
            envelope_store=envelope_store,
            claimset_store=claimset_store,
            semantic_proof_store=semantic_proof_store,
            composition_proof_store=composition_proof_store,
        )
        if outcome is not None:
            return result, outcome
        if result.error_codes != (
            _base.CompositionErrorCode.UNDECLARED_COMPOSITE_ADDITION.value,
        ):
            return result, None
        return self._compose_source_only_final_additions(
            result,
            h1,
            h2,
            heritage_store=heritage_store,
            envelope_store=envelope_store,
            claimset_store=claimset_store,
            semantic_proof_store=semantic_proof_store,
            composition_proof_store=composition_proof_store,
        )
