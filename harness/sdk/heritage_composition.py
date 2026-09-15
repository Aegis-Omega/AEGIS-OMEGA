"""AEGIS MHP-1 transitive semantic-lineage composition kernel v1.

This module is evidence-only. It never grants execution, admission, or canonical
control authority. The wire authority value is always ``NONE``.

The V1 composition surface deliberately does not accept a caller-authored
SemanticLineageEnvelopeV1. It resolves predecessor envelopes and ClaimSets from
trusted stores, derives the composed preservation/loss partition internally,
then verifies the constructed envelope before emitting a composition receipt.

Final composite additions remain fail-closed in V1 because a distinct
composition proof for DerivationProofReceiptV1 has not been ratified. Reusing a
predecessor derivation receipt would violate its exact transform_root binding.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Protocol

from harness.sdk.meaning_heritage import (
    DENIED,
    NO_AUTHORITY,
    PASS,
    ClaimSetReceiptV1,
    HeritageReceiptV1,
    HeritageVerificationResultV1,
    HeritageVerifierV13,
    LossType,
    PreservationEdge,
    PreservationProofReceiptV1,
    PreservationRelation,
    SemanticLineageEnvelopeV1,
    TransformRelation,
    TrustedClaimSetReceiptStore,
    TrustedHeritageReceiptStore,
    TrustedSemanticProofStore,
    VerificationErrorCode,
    canonical_hash,
    require_hash,
    require_id,
)

DOM_PRESERVATION_COMPOSITION_PROOF = "AEGIS_MHP1_PRESERVATION_COMPOSITION_PROOF_V1"
DOM_HERITAGE_COMPOSITION_RECEIPT = "AEGIS_MHP1_HERITAGE_COMPOSITION_RECEIPT_V1"
DOM_TRANSITIVE_TRANSFORM = "AEGIS_MHP1_TRANSITIVE_TRANSFORM_V1"
DOM_COMPOSED_PRESERVATION_SET = "AEGIS_MHP1_COMPOSED_PRESERVATION_SET_V1"
DOM_COMPOSED_OMISSION_SET = "AEGIS_MHP1_COMPOSED_OMISSION_SET_V1"
DOM_COMPOSED_ADDITION_SET = "AEGIS_MHP1_COMPOSED_ADDITION_SET_V1"
DOM_TRANSIENT_ELIMINATED_SET = "AEGIS_MHP1_TRANSIENT_ELIMINATED_SET_V1"
DOM_INTERMEDIATE_INHERITED_LOSS_SET = "AEGIS_MHP1_INTERMEDIATE_INHERITED_LOSS_SET_V1"
DOM_MIXED_ANCESTRY_SET = "AEGIS_MHP1_MIXED_ANCESTRY_SET_V1"


class CompositionErrorCode(str, Enum):
    TRANSIENT_ADDITION_LEAK = "TRANSIENT_ADDITION_LEAK"
    UNDECLARED_COMPOSITE_LOSS = "UNDECLARED_COMPOSITE_LOSS"
    UNDECLARED_COMPOSITE_ADDITION = "UNDECLARED_COMPOSITE_ADDITION"
    COMPOSITION_PRESERVATION_UNPROVEN = "COMPOSITION_PRESERVATION_UNPROVEN"
    COMPOSITION_MIXED_ANCESTRY = "COMPOSITION_MIXED_ANCESTRY"
    COMPOSITION_PARTITION_MISMATCH = "COMPOSITION_PARTITION_MISMATCH"


class TrustedSemanticLineageEnvelopeStore(Protocol):
    def fetch_verified(self, root: str) -> SemanticLineageEnvelopeV1 | None: ...


@dataclass(frozen=True)
class PreservationCompositionProofReceiptV1:
    left_proof_root: str
    right_proof_root: str
    source_claim_digest: str
    midpoint_claim_digest: str
    derived_claim_digest: str
    source_semantic_fingerprint: str
    midpoint_semantic_fingerprint: str
    derived_semantic_fingerprint: str
    relation: PreservationRelation
    verifier_root: str
    policy_root: str
    status: str = PASS
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.preservation-composition-proof-receipt.v1"

    def __post_init__(self) -> None:
        for name in (
            "left_proof_root",
            "right_proof_root",
            "source_claim_digest",
            "midpoint_claim_digest",
            "derived_claim_digest",
            "verifier_root",
            "policy_root",
        ):
            require_hash(name, getattr(self, name))
        for name in (
            "source_semantic_fingerprint",
            "midpoint_semantic_fingerprint",
            "derived_semantic_fingerprint",
        ):
            require_id(name, getattr(self, name))
        if self.status != PASS:
            raise ValueError("PRESERVATION_COMPOSITION_PROOF_NOT_PASS")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["relation"] = self.relation.value
        return canonical_hash(DOM_PRESERVATION_COMPOSITION_PROOF, data)


class TrustedPreservationCompositionProofStore(Protocol):
    def fetch_verified(self, root: str) -> PreservationCompositionProofReceiptV1 | None: ...

    def fetch_verified_for(
        self,
        *,
        left_proof_root: str,
        right_proof_root: str,
        source_claim_digest: str,
        midpoint_claim_digest: str,
        derived_claim_digest: str,
    ) -> PreservationCompositionProofReceiptV1 | None: ...


@dataclass(frozen=True)
class HeritageCompositionReceiptV1:
    left_heritage_receipt_root: str
    right_heritage_receipt_root: str
    midpoint_claimset_receipt_root: str
    composed_source_claimset_receipt_root: str
    composed_target_claimset_receipt_root: str
    composed_envelope_root: str
    composed_heritage_receipt_root: str
    composed_preservation_root: str
    composed_omissions_root: str
    composed_additions_root: str
    transient_eliminated_root: str
    intermediate_inherited_loss_root: str
    mixed_ancestry_root: str
    mixed_ancestry_count: int
    composition_verifier_root: str
    composition_policy_root: str
    status: str = PASS
    receipt_version: str = "aegis.heritage-composition-receipt.v1"
    authority_class: str = field(default=NO_AUTHORITY, init=False)

    def __post_init__(self) -> None:
        for name in (
            "left_heritage_receipt_root",
            "right_heritage_receipt_root",
            "midpoint_claimset_receipt_root",
            "composed_source_claimset_receipt_root",
            "composed_target_claimset_receipt_root",
            "composed_envelope_root",
            "composed_heritage_receipt_root",
            "composed_preservation_root",
            "composed_omissions_root",
            "composed_additions_root",
            "transient_eliminated_root",
            "intermediate_inherited_loss_root",
            "mixed_ancestry_root",
            "composition_verifier_root",
            "composition_policy_root",
        ):
            require_hash(name, getattr(self, name))
        if self.mixed_ancestry_count != 0:
            raise ValueError(CompositionErrorCode.COMPOSITION_MIXED_ANCESTRY.value)
        if self.status != PASS:
            raise ValueError("HERITAGE_COMPOSITION_NOT_PASS")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_HERITAGE_COMPOSITION_RECEIPT, asdict(self))


@dataclass(frozen=True)
class HeritageCompositionOutcomeV1:
    envelope: SemanticLineageEnvelopeV1
    heritage_receipt: HeritageReceiptV1
    composition_receipt: HeritageCompositionReceiptV1


class _CompositionAwareSemanticProofStore:
    def __init__(
        self,
        semantic_store: TrustedSemanticProofStore,
        composition_store: TrustedPreservationCompositionProofStore,
    ) -> None:
        self.semantic_store = semantic_store
        self.composition_store = composition_store

    def fetch_preservation(self, root: str):
        proof = self.semantic_store.fetch_preservation(root)
        if proof is not None:
            return proof
        return self.composition_store.fetch_verified(root)

    def fetch_derivation(self, root: str):
        return self.semantic_store.fetch_derivation(root)


def _set_root(domain: str, values: set[str]) -> str:
    return canonical_hash(domain, sorted(values))


def _preservation_root(edges: tuple[PreservationEdge, ...]) -> str:
    payload = sorted(
        (
            edge.source_claim_digest,
            edge.derived_claim_digest,
            edge.relation.value,
            edge.proof_receipt_root,
        )
        for edge in edges
    )
    return canonical_hash(DOM_COMPOSED_PRESERVATION_SET, payload)


def _deny(code: str) -> tuple[HeritageVerificationResultV1, None]:
    return HeritageVerificationResultV1(DENIED, (code,), None), None


class HeritageCompositionKernelV1:
    def __init__(self, *, verifier_root: str, policy_root: str) -> None:
        require_hash("verifier_root", verifier_root)
        require_hash("policy_root", policy_root)
        self.verifier_root = verifier_root
        self.policy_root = policy_root

    @staticmethod
    def _trusted_heritage(
        store: TrustedHeritageReceiptStore, receipt: HeritageReceiptV1
    ) -> bool:
        trusted = store.fetch_verified(receipt.root)
        return trusted is not None and trusted == receipt and trusted.root == receipt.root

    @staticmethod
    def _trusted_envelope(
        store: TrustedSemanticLineageEnvelopeStore, root: str
    ) -> SemanticLineageEnvelopeV1 | None:
        envelope = store.fetch_verified(root)
        if envelope is None or envelope.root != root:
            return None
        return envelope

    @staticmethod
    def _trusted_claimset(
        store: TrustedClaimSetReceiptStore, root: str
    ) -> ClaimSetReceiptV1 | None:
        receipt = store.fetch_verified(root)
        if receipt is None or receipt.root != root:
            return None
        return receipt

    @staticmethod
    def _edge_proof(
        edge: PreservationEdge,
        source_claimset: ClaimSetReceiptV1,
        derived_claimset: ClaimSetReceiptV1,
        semantic_store: TrustedSemanticProofStore,
    ) -> PreservationProofReceiptV1 | None:
        proof = semantic_store.fetch_preservation(edge.proof_receipt_root)
        if proof is None or proof.root != edge.proof_receipt_root:
            return None
        if (
            proof.source_claim_digest != edge.source_claim_digest
            or proof.derived_claim_digest != edge.derived_claim_digest
            or proof.relation != edge.relation
        ):
            return None
        src = source_claimset.claim_map.get(edge.source_claim_digest)
        der = derived_claimset.claim_map.get(edge.derived_claim_digest)
        if src is None or der is None:
            return None
        if (
            proof.source_semantic_fingerprint != src.semantic_fingerprint
            or proof.derived_semantic_fingerprint != der.semantic_fingerprint
        ):
            return None
        return proof

    def _compose_relation(
        self,
        *,
        left_edge: PreservationEdge,
        right_edge: PreservationEdge,
        left_proof: PreservationProofReceiptV1,
        right_proof: PreservationProofReceiptV1,
        c1: ClaimSetReceiptV1,
        c2: ClaimSetReceiptV1,
        c3: ClaimSetReceiptV1,
        composition_store: TrustedPreservationCompositionProofStore,
    ) -> tuple[PreservationRelation, str] | None:
        src = c1.claim_map[left_edge.source_claim_digest]
        mid = c2.claim_map[left_edge.derived_claim_digest]
        dst = c3.claim_map[right_edge.derived_claim_digest]

        if left_edge.relation == PreservationRelation.SAME_CLAIM_ROOT:
            if (
                src.claim_digest != mid.claim_digest
                or src.semantic_fingerprint != mid.semantic_fingerprint
            ):
                return None
            return right_edge.relation, right_edge.proof_receipt_root

        if right_edge.relation == PreservationRelation.SAME_CLAIM_ROOT:
            if (
                mid.claim_digest != dst.claim_digest
                or mid.semantic_fingerprint != dst.semantic_fingerprint
            ):
                return None
            return left_edge.relation, left_edge.proof_receipt_root

        proof = composition_store.fetch_verified_for(
            left_proof_root=left_edge.proof_receipt_root,
            right_proof_root=right_edge.proof_receipt_root,
            source_claim_digest=src.claim_digest,
            midpoint_claim_digest=mid.claim_digest,
            derived_claim_digest=dst.claim_digest,
        )
        if proof is None or composition_store.fetch_verified(proof.root) != proof:
            return None
        if (
            proof.left_proof_root != left_proof.root
            or proof.right_proof_root != right_proof.root
            or proof.source_claim_digest != src.claim_digest
            or proof.midpoint_claim_digest != mid.claim_digest
            or proof.derived_claim_digest != dst.claim_digest
            or proof.source_semantic_fingerprint != src.semantic_fingerprint
            or proof.midpoint_semantic_fingerprint != mid.semantic_fingerprint
            or proof.derived_semantic_fingerprint != dst.semantic_fingerprint
            or proof.verifier_root != self.verifier_root
            or proof.policy_root != self.policy_root
        ):
            return None
        return proof.relation, proof.root

    @staticmethod
    def _single_step_partition_ok(
        envelope: SemanticLineageEnvelopeV1,
        source: ClaimSetReceiptV1,
        derived: ClaimSetReceiptV1,
    ) -> bool:
        preserved_src = {edge.source_claim_digest for edge in envelope.preservation_edges}
        preserved_der = {edge.derived_claim_digest for edge in envelope.preservation_edges}
        omissions = set(envelope.declared_omission_digests)
        additions = {edge.derived_claim_digest for edge in envelope.declared_additions}
        src = set(source.claim_map)
        der = set(derived.claim_map)
        return (
            not (preserved_src & omissions)
            and not (preserved_der & additions)
            and src == preserved_src | omissions
            and der == preserved_der | additions
        )

    @staticmethod
    def _mixed_ancestry(
        e1: SemanticLineageEnvelopeV1,
        e2: SemanticLineageEnvelopeV1,
        semantic_store: TrustedSemanticProofStore,
    ) -> set[str]:
        descended_midpoints = {edge.derived_claim_digest for edge in e1.preservation_edges}
        intermediate_additions = {edge.derived_claim_digest for edge in e1.declared_additions}
        mixed: set[str] = set()
        for addition in e2.declared_additions:
            proof = semantic_store.fetch_derivation(addition.derivation_receipt_root)
            if proof is None or proof.root != addition.derivation_receipt_root:
                continue
            sources = set(proof.source_claim_digests)
            if sources & descended_midpoints and sources & intermediate_additions:
                mixed.add(addition.derived_claim_digest)
        return mixed

    @staticmethod
    def _loss_type(
        e1: SemanticLineageEnvelopeV1,
        e2: SemanticLineageEnvelopeV1,
        first_step_losses: set[str],
        inherited_losses: set[str],
    ) -> LossType | None:
        contributors: list[LossType] = []
        if first_step_losses:
            contributors.append(e1.loss_type)
        if inherited_losses:
            contributors.append(e2.loss_type)
        contributors = [item for item in contributors if item != LossType.EXACT_LOSSLESS]
        if not contributors:
            return LossType.EXACT_LOSSLESS
        if all(item == contributors[0] for item in contributors):
            return contributors[0]
        return None

    def compose(
        self,
        h1: HeritageReceiptV1,
        h2: HeritageReceiptV1,
        *,
        heritage_store: TrustedHeritageReceiptStore,
        envelope_store: TrustedSemanticLineageEnvelopeStore,
        claimset_store: TrustedClaimSetReceiptStore,
        semantic_proof_store: TrustedSemanticProofStore,
        composition_proof_store: TrustedPreservationCompositionProofStore,
    ) -> tuple[
        HeritageVerificationResultV1,
        HeritageCompositionOutcomeV1 | None,
    ]:
        if not self._trusted_heritage(heritage_store, h1) or not self._trusted_heritage(
            heritage_store, h2
        ):
            return _deny(VerificationErrorCode.PREDECESSOR_RECEIPT_INVALID.value)
        if (
            h1.derived_root != h2.source_root
            or h1.derived_claimset_receipt_root != h2.source_claimset_receipt_root
        ):
            return _deny(VerificationErrorCode.COMPOSITION_ENDPOINT_MISMATCH.value)

        e1 = self._trusted_envelope(envelope_store, h1.envelope_root)
        e2 = self._trusted_envelope(envelope_store, h2.envelope_root)
        if e1 is None or e2 is None:
            return _deny(VerificationErrorCode.PREDECESSOR_RECEIPT_INVALID.value)
        if (
            e1.source_root != h1.source_root
            or e1.source_claimset_receipt_root != h1.source_claimset_receipt_root
            or e1.derived_root != h1.derived_root
            or e1.derived_claimset_receipt_root != h1.derived_claimset_receipt_root
            or e1.transform_root != h1.transform_root
            or e2.source_root != h2.source_root
            or e2.source_claimset_receipt_root != h2.source_claimset_receipt_root
            or e2.derived_root != h2.derived_root
            or e2.derived_claimset_receipt_root != h2.derived_claimset_receipt_root
            or e2.transform_root != h2.transform_root
        ):
            return _deny(VerificationErrorCode.PREDECESSOR_RECEIPT_INVALID.value)

        c1 = self._trusted_claimset(claimset_store, h1.source_claimset_receipt_root)
        c2 = self._trusted_claimset(claimset_store, h1.derived_claimset_receipt_root)
        c3 = self._trusted_claimset(claimset_store, h2.derived_claimset_receipt_root)
        if c1 is None or c2 is None or c3 is None:
            return _deny(VerificationErrorCode.CLAIMSET_RECEIPT_UNTRUSTED.value)
        if (
            c1.payload_root != h1.source_root
            or c2.payload_root != h1.derived_root
            or c2.root != h2.source_claimset_receipt_root
            or c3.payload_root != h2.derived_root
        ):
            return _deny(VerificationErrorCode.COMPOSITION_ENDPOINT_MISMATCH.value)
        if not self._single_step_partition_ok(e1, c1, c2) or not self._single_step_partition_ok(
            e2, c2, c3
        ):
            return _deny(CompositionErrorCode.COMPOSITION_PARTITION_MISMATCH.value)

        right_by_source: dict[str, list[PreservationEdge]] = {}
        for edge in e2.preservation_edges:
            right_by_source.setdefault(edge.source_claim_digest, []).append(edge)

        composed: list[PreservationEdge] = []
        seen_pair_rel: dict[tuple[str, str], PreservationRelation] = {}
        for left_edge in e1.preservation_edges:
            left_proof = self._edge_proof(left_edge, c1, c2, semantic_proof_store)
            if left_proof is None:
                return _deny(VerificationErrorCode.PREDECESSOR_RECEIPT_INVALID.value)
            for right_edge in right_by_source.get(left_edge.derived_claim_digest, []):
                right_proof = self._edge_proof(right_edge, c2, c3, semantic_proof_store)
                if right_proof is None:
                    return _deny(VerificationErrorCode.PREDECESSOR_RECEIPT_INVALID.value)
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
                    return _deny(
                        CompositionErrorCode.COMPOSITION_PRESERVATION_UNPROVEN.value
                    )
                relation, proof_root = composed_relation
                pair = (left_edge.source_claim_digest, right_edge.derived_claim_digest)
                prior = seen_pair_rel.get(pair)
                if prior is not None and prior != relation:
                    return _deny(
                        CompositionErrorCode.COMPOSITION_PRESERVATION_UNPROVEN.value
                    )
                seen_pair_rel[pair] = relation
                edge = PreservationEdge(pair[0], pair[1], relation, proof_root)
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

        if transient & target_digests:
            return _deny(CompositionErrorCode.TRANSIENT_ADDITION_LEAK.value)
        if mixed:
            return _deny(CompositionErrorCode.COMPOSITION_MIXED_ANCESTRY.value)
        if o13 != o1 | inherited_loss:
            return _deny(CompositionErrorCode.UNDECLARED_COMPOSITE_LOSS.value)
        # V1 deliberately has no derivation-composition proof object. Any final
        # addition therefore remains unprovable at the composed transform root.
        if a13:
            return _deny(CompositionErrorCode.UNDECLARED_COMPOSITE_ADDITION.value)
        if (
            dom & o13
            or ran & a13
            or source_digests != dom | o13
            or target_digests != ran | a13
        ):
            return _deny(CompositionErrorCode.COMPOSITION_PARTITION_MISMATCH.value)

        loss_type = self._loss_type(e1, e2, o1, inherited_loss)
        if loss_type is None:
            return _deny(CompositionErrorCode.COMPOSITION_PARTITION_MISMATCH.value)

        if o13:
            relation = TransformRelation.LOSSY_TRANSFORM
        elif (
            h1.source_root == h2.derived_root
            and h1.source_claimset_receipt_root == h2.derived_claimset_receipt_root
            and all(
                edge.relation == PreservationRelation.SAME_CLAIM_ROOT
                for edge in composed_edges
            )
        ):
            relation = TransformRelation.IDENTITY
        else:
            relation = TransformRelation.LOSSLESS_TRANSFORM

        uncertainty_bps = 0 if not o13 else max(e1.uncertainty_bps, e2.uncertainty_bps)
        transform_root = canonical_hash(
            DOM_TRANSITIVE_TRANSFORM,
            {
                "left_envelope_root": e1.root,
                "right_envelope_root": e2.root,
                "left_transform_root": e1.transform_root,
                "right_transform_root": e2.transform_root,
                "composition_verifier_root": self.verifier_root,
                "composition_policy_root": self.policy_root,
            },
        )
        lineage_id = canonical_hash(
            "AEGIS_MHP1_TRANSITIVE_LINEAGE_ID_V1",
            {"left": e1.root, "right": e2.root, "transform_root": transform_root},
        )
        envelope = SemanticLineageEnvelopeV1(
            lineage_id=lineage_id,
            source_root=c1.payload_root,
            source_claimset_receipt_root=c1.root,
            derived_root=c3.payload_root,
            derived_claimset_receipt_root=c3.root,
            transform_root=transform_root,
            transform_relation=relation,
            loss_type=loss_type,
            preservation_edges=composed_edges,
            declared_omission_digests=tuple(sorted(o13)),
            declared_additions=(),
            uncertainty_bps=uncertainty_bps,
        )

        overlay = _CompositionAwareSemanticProofStore(
            semantic_proof_store, composition_proof_store
        )
        verifier = HeritageVerifierV13(
            verifier_root=self.verifier_root,
            policy_root=self.policy_root,
            proof_store=overlay,
            claimset_store=claimset_store,
            heritage_store=heritage_store,
        )
        result, heritage_receipt = verifier.verify(envelope, c1, c3, (h1, h2))
        if heritage_receipt is None or result.status != PASS:
            return result, None

        composition_receipt = HeritageCompositionReceiptV1(
            left_heritage_receipt_root=h1.root,
            right_heritage_receipt_root=h2.root,
            midpoint_claimset_receipt_root=c2.root,
            composed_source_claimset_receipt_root=c1.root,
            composed_target_claimset_receipt_root=c3.root,
            composed_envelope_root=envelope.root,
            composed_heritage_receipt_root=heritage_receipt.root,
            composed_preservation_root=_preservation_root(composed_edges),
            composed_omissions_root=_set_root(DOM_COMPOSED_OMISSION_SET, o13),
            composed_additions_root=_set_root(DOM_COMPOSED_ADDITION_SET, a13),
            transient_eliminated_root=_set_root(DOM_TRANSIENT_ELIMINATED_SET, transient),
            intermediate_inherited_loss_root=_set_root(
                DOM_INTERMEDIATE_INHERITED_LOSS_SET, inherited_loss
            ),
            mixed_ancestry_root=_set_root(DOM_MIXED_ANCESTRY_SET, mixed),
            mixed_ancestry_count=len(mixed),
            composition_verifier_root=self.verifier_root,
            composition_policy_root=self.policy_root,
        )
        return result, HeritageCompositionOutcomeV1(
            envelope=envelope,
            heritage_receipt=heritage_receipt,
            composition_receipt=composition_receipt,
        )
