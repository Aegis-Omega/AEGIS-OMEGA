"""AEGIS MHP-1 transitive semantic-lineage composition kernel v1.4.

This module extends the verified single-step V1.3 accounting model without
mutating its historical API. V1.4 composition accepts only predecessor receipts
and trusted resolution ports; the composed lineage envelope is derived
internally and every emitted receipt remains authority_class == "NONE".
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
    DeclaredAdditionEdge,
    DerivationProofReceiptV1,
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
    canonical_hash,
    require_hash,
    require_id,
)

DOM_PRESERVATION_COMPOSITION_PROOF = "AEGIS_MHP1_PRESERVATION_COMPOSITION_PROOF_V1"
DOM_COMPOSED_TRANSFORM = "AEGIS_MHP1_COMPOSED_TRANSFORM_V1"
DOM_HERITAGE_COMPOSITION_VERIFICATION = "AEGIS_MHP1_HERITAGE_COMPOSITION_VERIFICATION_V1"
DOM_HERITAGE_COMPOSITION_RECEIPT = "AEGIS_MHP1_HERITAGE_COMPOSITION_RECEIPT_V1"


class CompositionVerificationErrorCode(str, Enum):
    COMPOSITION_TRUST_STORE_REQUIRED = "COMPOSITION_TRUST_STORE_REQUIRED"
    COMPOSITION_PREDECESSOR_UNTRUSTED = "COMPOSITION_PREDECESSOR_UNTRUSTED"
    COMPOSITION_ENVELOPE_UNTRUSTED = "COMPOSITION_ENVELOPE_UNTRUSTED"
    COMPOSITION_CLAIMSET_UNTRUSTED = "COMPOSITION_CLAIMSET_UNTRUSTED"
    COMPOSITION_PROOF_UNTRUSTED = "COMPOSITION_PROOF_UNTRUSTED"
    COMPOSITION_ENDPOINT_MISMATCH = "COMPOSITION_ENDPOINT_MISMATCH"
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
    output_relation: PreservationRelation
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
        if self.output_relation == PreservationRelation.SAME_CLAIM_ROOT:
            if self.source_claim_digest != self.derived_claim_digest:
                raise ValueError("COMPOSED_SAME_CLAIM_ROOT_MISMATCH")
            if self.source_semantic_fingerprint != self.derived_semantic_fingerprint:
                raise ValueError("COMPOSED_SAME_CLAIM_ROOT_FINGERPRINT_MISMATCH")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["output_relation"] = self.output_relation.value
        return canonical_hash(DOM_PRESERVATION_COMPOSITION_PROOF, data)


class TrustedPreservationCompositionProofStore(Protocol):
    def fetch_verified(
        self,
        left_proof_root: str,
        right_proof_root: str,
    ) -> PreservationCompositionProofReceiptV1 | None: ...


@dataclass(frozen=True)
class HeritageCompositionReceiptV1:
    composed_envelope_root: str
    composed_transform_root: str
    source_root: str
    source_claimset_receipt_root: str
    derived_root: str
    derived_claimset_receipt_root: str
    predecessor_receipt_roots: tuple[str, str]
    predecessor_envelope_roots: tuple[str, str]
    preservation_edges: tuple[PreservationEdge, ...]
    omission_digests: tuple[str, ...]
    addition_digests: tuple[str, ...]
    transient_addition_digests: tuple[str, ...]
    intermediate_loss_digests: tuple[str, ...]
    mixed_ancestry_digests: tuple[str, ...]
    verification_root: str
    status: str = PASS
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.heritage-composition-receipt.v1"

    def __post_init__(self) -> None:
        for name in (
            "composed_envelope_root",
            "composed_transform_root",
            "source_root",
            "source_claimset_receipt_root",
            "derived_root",
            "derived_claimset_receipt_root",
            "verification_root",
        ):
            require_hash(name, getattr(self, name))
        for root in self.predecessor_receipt_roots + self.predecessor_envelope_roots:
            require_hash("predecessor_root", root)
        for digest in (
            self.omission_digests
            + self.addition_digests
            + self.transient_addition_digests
            + self.intermediate_loss_digests
            + self.mixed_ancestry_digests
        ):
            require_hash("composition_digest", digest)
        if self.status != PASS:
            raise ValueError("HERITAGE_COMPOSITION_RECEIPT_NOT_PASS")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["preservation_edges"] = [
            {
                "source_claim_digest": edge.source_claim_digest,
                "derived_claim_digest": edge.derived_claim_digest,
                "relation": edge.relation.value,
                "proof_receipt_root": edge.proof_receipt_root,
            }
            for edge in self.preservation_edges
        ]
        return canonical_hash(DOM_HERITAGE_COMPOSITION_RECEIPT, data)


class HeritageVerifierV14(HeritageVerifierV13):
    """V1.3 single-step verification plus fail-closed transitive composition."""

    @staticmethod
    def _deny(*codes: str):
        return (
            HeritageVerificationResultV1(DENIED, tuple(sorted(set(codes))), None),
            None,
            None,
        )

    @staticmethod
    def _trusted_receipt(
        store: TrustedHeritageReceiptStore,
        receipt: HeritageReceiptV1,
    ) -> bool:
        trusted = store.fetch_verified(receipt.root)
        return trusted is not None and trusted == receipt and trusted.root == receipt.root

    @staticmethod
    def _trusted_envelope(
        store: TrustedSemanticLineageEnvelopeStore,
        root: str,
    ) -> SemanticLineageEnvelopeV1 | None:
        envelope = store.fetch_verified(root)
        if envelope is None or envelope.root != root:
            return None
        return envelope

    @staticmethod
    def _trusted_claimset(
        store: TrustedClaimSetReceiptStore,
        root: str,
    ) -> ClaimSetReceiptV1 | None:
        receipt = store.fetch_verified(root)
        if receipt is None or receipt.root != root:
            return None
        return receipt

    @staticmethod
    def _trusted_preservation(
        store: TrustedSemanticProofStore,
        edge: PreservationEdge,
        source_claimset: ClaimSetReceiptV1,
        derived_claimset: ClaimSetReceiptV1,
    ) -> PreservationProofReceiptV1 | None:
        proof = store.fetch_preservation(edge.proof_receipt_root)
        if proof is None or proof.root != edge.proof_receipt_root:
            return None
        if (
            proof.source_claim_digest != edge.source_claim_digest
            or proof.derived_claim_digest != edge.derived_claim_digest
            or proof.relation != edge.relation
        ):
            return None
        source_claim = source_claimset.claim_map.get(edge.source_claim_digest)
        derived_claim = derived_claimset.claim_map.get(edge.derived_claim_digest)
        if source_claim is None or derived_claim is None:
            return None
        if (
            proof.source_semantic_fingerprint != source_claim.semantic_fingerprint
            or proof.derived_semantic_fingerprint != derived_claim.semantic_fingerprint
        ):
            return None
        return proof

    @staticmethod
    def _composed_loss_type(
        left: SemanticLineageEnvelopeV1,
        right: SemanticLineageEnvelopeV1,
        has_loss: bool,
    ) -> LossType:
        if not has_loss:
            return LossType.EXACT_LOSSLESS
        non_exact = tuple(
            item
            for item in (left.loss_type, right.loss_type)
            if item != LossType.EXACT_LOSSLESS
        )
        if not non_exact:
            return LossType.STRUCTURAL_PROJECTION
        if all(item == non_exact[0] for item in non_exact):
            return non_exact[0]
        return LossType.HEURISTIC_ABSTRACTION

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
        SemanticLineageEnvelopeV1 | None,
        HeritageCompositionReceiptV1 | None,
    ]:
        errors: list[str] = []

        if not self._trusted_receipt(heritage_store, h1) or not self._trusted_receipt(
            heritage_store, h2
        ):
            return self._deny(
                CompositionVerificationErrorCode.COMPOSITION_PREDECESSOR_UNTRUSTED.value
            )
        if (
            h1.derived_root != h2.source_root
            or h1.derived_claimset_receipt_root != h2.source_claimset_receipt_root
        ):
            return self._deny(
                CompositionVerificationErrorCode.COMPOSITION_ENDPOINT_MISMATCH.value
            )

        e1 = self._trusted_envelope(envelope_store, h1.envelope_root)
        e2 = self._trusted_envelope(envelope_store, h2.envelope_root)
        if e1 is None or e2 is None:
            return self._deny(
                CompositionVerificationErrorCode.COMPOSITION_ENVELOPE_UNTRUSTED.value
            )
        if (
            e1.source_root != h1.source_root
            or e1.source_claimset_receipt_root != h1.source_claimset_receipt_root
            or e1.derived_root != h1.derived_root
            or e1.derived_claimset_receipt_root != h1.derived_claimset_receipt_root
            or e2.source_root != h2.source_root
            or e2.source_claimset_receipt_root != h2.source_claimset_receipt_root
            or e2.derived_root != h2.derived_root
            or e2.derived_claimset_receipt_root != h2.derived_claimset_receipt_root
        ):
            return self._deny(
                CompositionVerificationErrorCode.COMPOSITION_ENVELOPE_UNTRUSTED.value
            )

        c1 = self._trusted_claimset(claimset_store, h1.source_claimset_receipt_root)
        c2 = self._trusted_claimset(claimset_store, h1.derived_claimset_receipt_root)
        c3 = self._trusted_claimset(claimset_store, h2.derived_claimset_receipt_root)
        if c1 is None or c2 is None or c3 is None:
            return self._deny(
                CompositionVerificationErrorCode.COMPOSITION_CLAIMSET_UNTRUSTED.value
            )
        if (
            c1.payload_root != h1.source_root
            or c2.payload_root != h1.derived_root
            or c2.root != h2.source_claimset_receipt_root
            or c3.payload_root != h2.derived_root
        ):
            return self._deny(
                CompositionVerificationErrorCode.COMPOSITION_CLAIMSET_UNTRUSTED.value
            )

        p1_by_mid: dict[str, list[tuple[PreservationEdge, PreservationProofReceiptV1]]] = {}
        p2_by_mid: dict[str, list[tuple[PreservationEdge, PreservationProofReceiptV1]]] = {}
        for edge in e1.preservation_edges:
            proof = self._trusted_preservation(semantic_proof_store, edge, c1, c2)
            if proof is None:
                errors.append(
                    CompositionVerificationErrorCode.COMPOSITION_PROOF_UNTRUSTED.value
                )
                continue
            p1_by_mid.setdefault(edge.derived_claim_digest, []).append((edge, proof))
        for edge in e2.preservation_edges:
            proof = self._trusted_preservation(semantic_proof_store, edge, c2, c3)
            if proof is None:
                errors.append(
                    CompositionVerificationErrorCode.COMPOSITION_PROOF_UNTRUSTED.value
                )
                continue
            p2_by_mid.setdefault(edge.source_claim_digest, []).append((edge, proof))
        if errors:
            return self._deny(*errors)

        composed: dict[tuple[str, str, str], tuple[PreservationEdge, str]] = {}
        mixed_final: set[str] = set()
        for midpoint in sorted(set(p1_by_mid) & set(p2_by_mid)):
            mid_claim = c2.claim_map[midpoint]
            for left_edge, left_proof in p1_by_mid[midpoint]:
                for right_edge, right_proof in p2_by_mid[midpoint]:
                    source_claim = c1.claim_map[left_edge.source_claim_digest]
                    derived_claim = c3.claim_map[right_edge.derived_claim_digest]
                    if left_edge.relation == PreservationRelation.SAME_CLAIM_ROOT:
                        relation = right_edge.relation
                        proof_root = right_edge.proof_receipt_root
                    elif right_edge.relation == PreservationRelation.SAME_CLAIM_ROOT:
                        relation = left_edge.relation
                        proof_root = left_edge.proof_receipt_root
                    else:
                        cp = composition_proof_store.fetch_verified(
                            left_edge.proof_receipt_root,
                            right_edge.proof_receipt_root,
                        )
                        if cp is None:
                            errors.append(
                                CompositionVerificationErrorCode.COMPOSITION_PRESERVATION_UNPROVEN.value
                            )
                            continue
                        if (
                            cp.left_proof_root != left_edge.proof_receipt_root
                            or cp.right_proof_root != right_edge.proof_receipt_root
                            or cp.source_claim_digest != left_edge.source_claim_digest
                            or cp.midpoint_claim_digest != midpoint
                            or cp.derived_claim_digest != right_edge.derived_claim_digest
                            or cp.source_semantic_fingerprint
                            != source_claim.semantic_fingerprint
                            or cp.midpoint_semantic_fingerprint
                            != mid_claim.semantic_fingerprint
                            or cp.derived_semantic_fingerprint
                            != derived_claim.semantic_fingerprint
                        ):
                            errors.append(
                                CompositionVerificationErrorCode.COMPOSITION_PROOF_UNTRUSTED.value
                            )
                            continue
                        relation = cp.output_relation
                        proof_root = cp.root

                    key = (
                        left_edge.source_claim_digest,
                        right_edge.derived_claim_digest,
                        relation.value,
                    )
                    candidate = PreservationEdge(
                        left_edge.source_claim_digest,
                        right_edge.derived_claim_digest,
                        relation,
                        proof_root,
                    )
                    previous = composed.get(key)
                    if previous is not None and previous[1] != midpoint:
                        mixed_final.add(right_edge.derived_claim_digest)
                    else:
                        composed[key] = (candidate, midpoint)

        if errors:
            return self._deny(*errors)

        p13 = tuple(
            item[0]
            for _, item in sorted(
                composed.items(),
                key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]),
            )
        )
        dom13 = {edge.source_claim_digest for edge in p13}
        ran13 = {edge.derived_claim_digest for edge in p13}
        c1_digests = set(c1.sorted_claim_digests)
        c2_digests = set(c2.sorted_claim_digests)
        c3_digests = set(c3.sorted_claim_digests)
        o13 = c1_digests - dom13
        a13 = c3_digests - ran13

        o1 = set(e1.declared_omission_digests)
        o2 = set(e2.declared_omission_digests)
        a1_map = {item.derived_claim_digest: item for item in e1.declared_additions}
        a2_map = {item.derived_claim_digest: item for item in e2.declared_additions}
        a1 = set(a1_map)
        a2 = set(a2_map)
        ran1 = {edge.derived_claim_digest for edge in e1.preservation_edges}

        explained_loss = o1 | {
            edge.source_claim_digest
            for edge in e1.preservation_edges
            if edge.derived_claim_digest in o2
        }
        if o13 - explained_loss:
            errors.append(
                CompositionVerificationErrorCode.UNDECLARED_COMPOSITE_LOSS.value
            )

        transient_additions = a1 & o2
        intermediate_losses = ran1 & o2
        a2_derivations: dict[str, DerivationProofReceiptV1] = {}
        for digest, addition in a2_map.items():
            proof = semantic_proof_store.fetch_derivation(addition.derivation_receipt_root)
            if proof is None or proof.root != addition.derivation_receipt_root:
                errors.append(
                    CompositionVerificationErrorCode.COMPOSITION_PROOF_UNTRUSTED.value
                )
                continue
            a2_derivations[digest] = proof
            sources = set(proof.source_claim_digests)
            if sources & transient_additions:
                errors.append(
                    CompositionVerificationErrorCode.TRANSIENT_ADDITION_LEAK.value
                )
            if sources & ran1 and sources & a1:
                mixed_final.add(digest)

        if mixed_final:
            errors.append(
                CompositionVerificationErrorCode.COMPOSITION_MIXED_ANCESTRY.value
            )

        composite_additions: list[DeclaredAdditionEdge] = []
        explained_additions: set[str] = set(a2)
        for digest in sorted(a13):
            if digest in a2_map:
                composite_additions.append(a2_map[digest])
                continue
            same_transport = [
                edge
                for edge in e2.preservation_edges
                if edge.source_claim_digest in a1
                and edge.derived_claim_digest == digest
                and edge.relation == PreservationRelation.SAME_CLAIM_ROOT
                and edge.source_claim_digest == edge.derived_claim_digest
            ]
            if len(same_transport) == 1:
                source_digest = same_transport[0].source_claim_digest
                composite_additions.append(
                    DeclaredAdditionEdge(
                        digest,
                        a1_map[source_digest].derivation_receipt_root,
                    )
                )
                explained_additions.add(digest)
            else:
                errors.append(
                    CompositionVerificationErrorCode.UNDECLARED_COMPOSITE_ADDITION.value
                )

        if a13 - explained_additions:
            errors.append(
                CompositionVerificationErrorCode.UNDECLARED_COMPOSITE_ADDITION.value
            )

        if (
            dom13 & o13
            or dom13 | o13 != c1_digests
            or ran13 & a13
            or ran13 | a13 != c3_digests
            or (ran1 | a1) != c2_digests
            or (ran1 & a1)
        ):
            errors.append(
                CompositionVerificationErrorCode.COMPOSITION_PARTITION_MISMATCH.value
            )

        if errors:
            return self._deny(*errors)

        if o13:
            transform_relation = TransformRelation.LOSSY_TRANSFORM
        elif a13:
            transform_relation = TransformRelation.AUGMENTING_TRANSFORM
        elif (
            h1.source_root == h2.derived_root
            and h1.source_claimset_receipt_root == h2.derived_claimset_receipt_root
            and all(
                edge.relation == PreservationRelation.SAME_CLAIM_ROOT for edge in p13
            )
        ):
            transform_relation = TransformRelation.IDENTITY
        else:
            transform_relation = TransformRelation.LOSSLESS_TRANSFORM

        loss_type = self._composed_loss_type(e1, e2, bool(o13))
        uncertainty_bps = min(10000, e1.uncertainty_bps + e2.uncertainty_bps)
        transform_root = canonical_hash(
            DOM_COMPOSED_TRANSFORM,
            {
                "left_transform_root": e1.transform_root,
                "right_transform_root": e2.transform_root,
                "left_receipt_root": h1.root,
                "right_receipt_root": h2.root,
                "policy_root": self.policy_root,
            },
        )
        composed_envelope = SemanticLineageEnvelopeV1(
            lineage_id=f"composition:{h1.root}:{h2.root}",
            source_root=c1.payload_root,
            source_claimset_receipt_root=c1.root,
            derived_root=c3.payload_root,
            derived_claimset_receipt_root=c3.root,
            transform_root=transform_root,
            transform_relation=transform_relation,
            loss_type=loss_type,
            preservation_edges=p13,
            declared_omission_digests=tuple(sorted(o13)),
            declared_additions=tuple(sorted(composite_additions, key=lambda x: x.derived_claim_digest)),
            uncertainty_bps=uncertainty_bps,
        )

        if (
            c1_digests
            != {edge.source_claim_digest for edge in composed_envelope.preservation_edges}
            | set(composed_envelope.declared_omission_digests)
            or c3_digests
            != {edge.derived_claim_digest for edge in composed_envelope.preservation_edges}
            | {item.derived_claim_digest for item in composed_envelope.declared_additions}
            or mixed_final
        ):
            return self._deny(
                CompositionVerificationErrorCode.COMPOSITION_PARTITION_MISMATCH.value
            )

        verification_root = canonical_hash(
            DOM_HERITAGE_COMPOSITION_VERIFICATION,
            {
                "composed_envelope_root": composed_envelope.root,
                "predecessor_receipt_roots": [h1.root, h2.root],
                "predecessor_envelope_roots": [e1.root, e2.root],
                "omission_digests": sorted(o13),
                "addition_digests": sorted(a13),
                "transient_addition_digests": sorted(transient_additions),
                "intermediate_loss_digests": sorted(intermediate_losses),
                "mixed_ancestry_digests": [],
                "verifier_root": self.verifier_root,
                "policy_root": self.policy_root,
                "status": PASS,
                "authority_class": NO_AUTHORITY,
            },
        )
        receipt = HeritageCompositionReceiptV1(
            composed_envelope_root=composed_envelope.root,
            composed_transform_root=transform_root,
            source_root=c1.payload_root,
            source_claimset_receipt_root=c1.root,
            derived_root=c3.payload_root,
            derived_claimset_receipt_root=c3.root,
            predecessor_receipt_roots=(h1.root, h2.root),
            predecessor_envelope_roots=(e1.root, e2.root),
            preservation_edges=p13,
            omission_digests=tuple(sorted(o13)),
            addition_digests=tuple(sorted(a13)),
            transient_addition_digests=tuple(sorted(transient_additions)),
            intermediate_loss_digests=tuple(sorted(intermediate_losses)),
            mixed_ancestry_digests=(),
            verification_root=verification_root,
        )
        return (
            HeritageVerificationResultV1(PASS, (), verification_root),
            composed_envelope,
            receipt,
        )
