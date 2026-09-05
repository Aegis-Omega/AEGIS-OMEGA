"""AEGIS antropolimorphic morphism verification engine v1.1.

Morphism envelopes and receipts are evidence subjects, never authority. Every
proof-bearing root must resolve through a trusted store, match the exact subject
and proof-obligation kind, and composition requires its own authenticated proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol, TypeAlias

from harness.sdk.meaning_heritage import (
    HeritageReceiptV1,
    TrustedHeritageReceiptStore,
    canonical_hash,
    require_hash,
    require_id,
)

DOM_MORPHISM_ENVELOPE = "AEGIS_MORPHISM_ENVELOPE_V1"
DOM_MORPHISM_VERIFICATION = "AEGIS_MORPHISM_VERIFICATION_V1"
DOM_MORPHISM_RECEIPT = "AEGIS_MORPHISM_RECEIPT_V1"
DOM_MORPHISM_COMPOSITION = "AEGIS_MORPHISM_COMPOSITION_V1"
DOM_MORPHISM_COMPOSITION_PROOF = "AEGIS_MORPHISM_COMPOSITION_PROOF_V1"
DOM_MORPHISM_PROOF_ARTIFACT = "AEGIS_MORPHISM_PROOF_ARTIFACT_V1"

NO_AUTHORITY = "NONE"
PASS = "PASS"
DENIED = "FAIL_MORPHISM_DENIED"


class MorphismError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class MorphismKind(str, Enum):
    CARRIER = "CARRIER"
    SPACE = "SPACE"
    REPRESENTATION = "REPRESENTATION"
    LIMIT = "LIMIT"
    SEMANTIC = "SEMANTIC"
    HERITAGE = "HERITAGE"


class ProofArtifactKind(str, Enum):
    CARRIER_TRANSPORT = "CARRIER_TRANSPORT"
    SPACE_IMAGE_MEMBERSHIP = "SPACE_IMAGE_MEMBERSHIP"
    SPACE_ADMISSIBILITY = "SPACE_ADMISSIBILITY"
    SPACE_BOUNDARY = "SPACE_BOUNDARY"
    REPRESENTATION_LEFT_INVERSE = "REPRESENTATION_LEFT_INVERSE"
    REPRESENTATION_RIGHT_INVERSE = "REPRESENTATION_RIGHT_INVERSE"
    REPRESENTATION_OBSERVABLE_COMMUTATION = "REPRESENTATION_OBSERVABLE_COMMUTATION"
    LIMIT_CONVERGENCE = "LIMIT_CONVERGENCE"
    LIMIT_UNIVERSAL_PROPERTY = "LIMIT_UNIVERSAL_PROPERTY"
    SEMANTIC_SOUNDNESS = "SEMANTIC_SOUNDNESS"
    SEMANTIC_CORRESPONDENCE = "SEMANTIC_CORRESPONDENCE"
    SEMANTIC_COMPLETENESS = "SEMANTIC_COMPLETENESS"


@dataclass(frozen=True)
class TheoremContextV1:
    theorem_digest: str
    carrier_root: str
    hypotheses_root: str
    normalization_root: str
    proof_context_root: str

    def __post_init__(self) -> None:
        for name in (
            "theorem_digest",
            "carrier_root",
            "hypotheses_root",
            "normalization_root",
            "proof_context_root",
        ):
            require_hash(name, getattr(self, name))


@dataclass(frozen=True)
class CarrierProofObligationV1:
    source_theorem: TheoremContextV1
    target_theorem: TheoremContextV1
    transport_map_root: str
    transport_proof_receipt_root: str

    def __post_init__(self) -> None:
        require_hash("transport_map_root", self.transport_map_root)
        require_hash("transport_proof_receipt_root", self.transport_proof_receipt_root)


@dataclass(frozen=True)
class SpaceProofObligationV1:
    subject_root: str
    source_space_root: str
    target_space_root: str
    image_membership_receipt_root: str
    admissibility_receipt_root: str
    boundary_condition_receipt_root: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "subject_root",
            "source_space_root",
            "target_space_root",
            "image_membership_receipt_root",
            "admissibility_receipt_root",
        ):
            require_hash(name, getattr(self, name))
        if self.boundary_condition_receipt_root is not None:
            require_hash("boundary_condition_receipt_root", self.boundary_condition_receipt_root)


@dataclass(frozen=True)
class RepresentationProofObligationV1:
    source_representation_root: str
    target_representation_root: str
    forward_map_root: str
    inverse_map_root: str
    left_inverse_proof_root: str
    right_inverse_proof_root: str
    observable_commutation_proof_root: str

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            require_hash(name, getattr(self, name))


@dataclass(frozen=True)
class LimitProofObligationV1:
    diagram_root: str
    index_filter_root: str
    topology_root: str
    limit_object_root: str
    convergence_theorem_receipt_root: str
    universal_property_receipt_root: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "diagram_root",
            "index_filter_root",
            "topology_root",
            "limit_object_root",
            "convergence_theorem_receipt_root",
        ):
            require_hash(name, getattr(self, name))
        if self.universal_property_receipt_root is not None:
            require_hash("universal_property_receipt_root", self.universal_property_receipt_root)


@dataclass(frozen=True)
class SemanticProofObligationV1:
    formal_object_root: str
    target_semantics_root: str
    convention_root: str
    soundness_receipt_root: str
    correspondence_receipt_root: str
    completeness_receipt_root: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "formal_object_root",
            "target_semantics_root",
            "convention_root",
            "soundness_receipt_root",
            "correspondence_receipt_root",
        ):
            require_hash(name, getattr(self, name))
        if self.completeness_receipt_root is not None:
            require_hash("completeness_receipt_root", self.completeness_receipt_root)


@dataclass(frozen=True)
class HeritageProofObligationV1:
    lineage_envelope_root: str
    heritage_receipt_root: str

    def __post_init__(self) -> None:
        require_hash("lineage_envelope_root", self.lineage_envelope_root)
        require_hash("heritage_receipt_root", self.heritage_receipt_root)


ProofObligation: TypeAlias = (
    CarrierProofObligationV1
    | SpaceProofObligationV1
    | RepresentationProofObligationV1
    | LimitProofObligationV1
    | SemanticProofObligationV1
    | HeritageProofObligationV1
)

_EXPECTED_OBLIGATION_TYPE: dict[MorphismKind, type] = {
    MorphismKind.CARRIER: CarrierProofObligationV1,
    MorphismKind.SPACE: SpaceProofObligationV1,
    MorphismKind.REPRESENTATION: RepresentationProofObligationV1,
    MorphismKind.LIMIT: LimitProofObligationV1,
    MorphismKind.SEMANTIC: SemanticProofObligationV1,
    MorphismKind.HERITAGE: HeritageProofObligationV1,
}


@dataclass(frozen=True)
class MorphismEnvelopeV1:
    morphism_id: str
    kind: MorphismKind
    source_domain_root: str
    target_domain_root: str
    proof_obligation: ProofObligation
    schema_version: str = "aegis.morphism-envelope.v1"

    def __post_init__(self) -> None:
        require_id("morphism_id", self.morphism_id)
        require_hash("source_domain_root", self.source_domain_root)
        require_hash("target_domain_root", self.target_domain_root)
        expected = _EXPECTED_OBLIGATION_TYPE[self.kind]
        if not isinstance(self.proof_obligation, expected):
            raise MorphismError("MORPHISM_KIND_OBLIGATION_MISMATCH")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["kind"] = self.kind.value
        return canonical_hash(DOM_MORPHISM_ENVELOPE, data)


@dataclass(frozen=True)
class ProofArtifactReceiptV1:
    proof_kind: ProofArtifactKind
    subject_root: str
    verifier_root: str
    policy_root: str
    status: str
    proof_context_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)

    def __post_init__(self) -> None:
        for name in ("subject_root", "verifier_root", "policy_root", "proof_context_root"):
            require_hash(name, getattr(self, name))
        if self.status != PASS:
            raise MorphismError("PROOF_ARTIFACT_NOT_PASS")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["proof_kind"] = self.proof_kind.value
        return canonical_hash(DOM_MORPHISM_PROOF_ARTIFACT, data)


class TrustedProofArtifactStore(Protocol):
    def fetch_verified(self, root: str) -> ProofArtifactReceiptV1 | None: ...


class TrustedMorphismReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> "MorphismReceiptV1 | None": ...


@dataclass(frozen=True)
class CompositionProofReceiptV1:
    left_morphism_root: str
    right_morphism_root: str
    composed_envelope_root: str
    midpoint_domain_root: str
    interface_contract_root: str
    verifier_root: str
    policy_root: str
    status: str = PASS
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.morphism-composition-proof.v1"

    def __post_init__(self) -> None:
        for name in (
            "left_morphism_root",
            "right_morphism_root",
            "composed_envelope_root",
            "midpoint_domain_root",
            "interface_contract_root",
            "verifier_root",
            "policy_root",
        ):
            require_hash(name, getattr(self, name))
        if self.status != PASS:
            raise MorphismError("COMPOSITION_PROOF_NOT_PASS")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_MORPHISM_COMPOSITION_PROOF, asdict(self))


class TrustedCompositionProofStore(Protocol):
    def fetch_verified(self, root: str) -> CompositionProofReceiptV1 | None: ...


@dataclass(frozen=True)
class MorphismVerificationResultV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class MorphismReceiptV1:
    envelope_root: str
    kind: MorphismKind
    source_domain_root: str
    target_domain_root: str
    verification_root: str
    verifier_root: str
    policy_root: str
    predecessor_morphism_roots: tuple[str, ...]
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.morphism-receipt.v1"

    def __post_init__(self) -> None:
        for name in (
            "envelope_root",
            "source_domain_root",
            "target_domain_root",
            "verification_root",
            "verifier_root",
            "policy_root",
        ):
            require_hash(name, getattr(self, name))
        for root in self.predecessor_morphism_roots:
            require_hash("predecessor_morphism_root", root)
        if len(self.predecessor_morphism_roots) != len(set(self.predecessor_morphism_roots)):
            raise MorphismError("PREDECESSOR_MORPHISM_DUPLICATE")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["predecessor_morphism_roots"] = sorted(self.predecessor_morphism_roots)
        return canonical_hash(DOM_MORPHISM_RECEIPT, data)

    @classmethod
    def _issue(
        cls,
        *,
        envelope: MorphismEnvelopeV1,
        verification_root: str,
        verifier_root: str,
        policy_root: str,
        predecessor_morphism_roots: tuple[str, ...],
    ) -> "MorphismReceiptV1":
        return cls(
            envelope_root=envelope.root,
            kind=envelope.kind,
            source_domain_root=envelope.source_domain_root,
            target_domain_root=envelope.target_domain_root,
            verification_root=verification_root,
            verifier_root=verifier_root,
            policy_root=policy_root,
            predecessor_morphism_roots=tuple(sorted(predecessor_morphism_roots)),
        )


class KindVerifier(Protocol):
    verifier_root: str
    policy_root: str
    kind: MorphismKind

    def verify(self, envelope: MorphismEnvelopeV1) -> tuple[str, ...]: ...


class _ReceiptBackedVerifier:
    def __init__(
        self,
        *,
        kind: MorphismKind,
        verifier_root: str,
        policy_root: str,
        proof_store: TrustedProofArtifactStore,
    ) -> None:
        require_hash("verifier_root", verifier_root)
        require_hash("policy_root", policy_root)
        self.kind = kind
        self.verifier_root = verifier_root
        self.policy_root = policy_root
        self.proof_store = proof_store

    def _require_proof(
        self,
        root: str,
        subject_root: str,
        expected_kind: ProofArtifactKind,
        code: str,
    ) -> str | None:
        receipt = self.proof_store.fetch_verified(root)
        if (
            receipt is None
            or receipt.root != root
            or receipt.subject_root != subject_root
            or receipt.proof_kind != expected_kind
        ):
            return code
        return None


class CarrierVerifierV1(_ReceiptBackedVerifier):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(kind=MorphismKind.CARRIER, **kwargs)

    def verify(self, envelope: MorphismEnvelopeV1) -> tuple[str, ...]:
        o = envelope.proof_obligation
        assert isinstance(o, CarrierProofObligationV1)
        errors: list[str] = []
        if (
            envelope.source_domain_root != o.source_theorem.carrier_root
            or envelope.target_domain_root != o.target_theorem.carrier_root
        ):
            errors.append("CARRIER_ENDPOINT_BINDING_FAILURE")
        subject = canonical_hash(
            "AEGIS_CARRIER_TRANSPORT_SUBJECT_V1",
            {
                "source": asdict(o.source_theorem),
                "target": asdict(o.target_theorem),
                "transport_map_root": o.transport_map_root,
            },
        )
        err = self._require_proof(
            o.transport_proof_receipt_root,
            subject,
            ProofArtifactKind.CARRIER_TRANSPORT,
            "CARRIER_TRANSPORT_PROOF_INVALID",
        )
        if err:
            errors.append(err)
        return tuple(sorted(set(errors)))


class SpaceVerifierV1(_ReceiptBackedVerifier):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(kind=MorphismKind.SPACE, **kwargs)

    def verify(self, envelope: MorphismEnvelopeV1) -> tuple[str, ...]:
        o = envelope.proof_obligation
        assert isinstance(o, SpaceProofObligationV1)
        errors: list[str] = []
        if (
            envelope.source_domain_root != o.source_space_root
            or envelope.target_domain_root != o.target_space_root
        ):
            errors.append("SPACE_ENDPOINT_BINDING_FAILURE")
        subject = canonical_hash(
            "AEGIS_SPACE_SUBJECT_V1",
            {
                "subject_root": o.subject_root,
                "source_space_root": o.source_space_root,
                "target_space_root": o.target_space_root,
            },
        )
        for root, kind, code in (
            (
                o.image_membership_receipt_root,
                ProofArtifactKind.SPACE_IMAGE_MEMBERSHIP,
                "SPACE_IMAGE_MEMBERSHIP_INVALID",
            ),
            (
                o.admissibility_receipt_root,
                ProofArtifactKind.SPACE_ADMISSIBILITY,
                "SPACE_ADMISSIBILITY_INVALID",
            ),
        ):
            err = self._require_proof(root, subject, kind, code)
            if err:
                errors.append(err)
        if o.boundary_condition_receipt_root:
            err = self._require_proof(
                o.boundary_condition_receipt_root,
                subject,
                ProofArtifactKind.SPACE_BOUNDARY,
                "SPACE_BOUNDARY_INVALID",
            )
            if err:
                errors.append(err)
        return tuple(sorted(set(errors)))


class RepresentationVerifierV1(_ReceiptBackedVerifier):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(kind=MorphismKind.REPRESENTATION, **kwargs)

    def verify(self, envelope: MorphismEnvelopeV1) -> tuple[str, ...]:
        o = envelope.proof_obligation
        assert isinstance(o, RepresentationProofObligationV1)
        errors: list[str] = []
        if (
            envelope.source_domain_root != o.source_representation_root
            or envelope.target_domain_root != o.target_representation_root
        ):
            errors.append("REPRESENTATION_ENDPOINT_BINDING_FAILURE")
        subject = canonical_hash(
            "AEGIS_REPRESENTATION_ISOMORPHISM_SUBJECT_V1",
            {
                "source": o.source_representation_root,
                "target": o.target_representation_root,
                "forward": o.forward_map_root,
                "inverse": o.inverse_map_root,
            },
        )
        for root, kind, code in (
            (
                o.left_inverse_proof_root,
                ProofArtifactKind.REPRESENTATION_LEFT_INVERSE,
                "REPRESENTATION_LEFT_INVERSE_INVALID",
            ),
            (
                o.right_inverse_proof_root,
                ProofArtifactKind.REPRESENTATION_RIGHT_INVERSE,
                "REPRESENTATION_RIGHT_INVERSE_INVALID",
            ),
            (
                o.observable_commutation_proof_root,
                ProofArtifactKind.REPRESENTATION_OBSERVABLE_COMMUTATION,
                "REPRESENTATION_COMMUTATION_INVALID",
            ),
        ):
            err = self._require_proof(root, subject, kind, code)
            if err:
                errors.append(err)
        return tuple(sorted(set(errors)))


class LimitVerifierV1(_ReceiptBackedVerifier):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(kind=MorphismKind.LIMIT, **kwargs)

    def verify(self, envelope: MorphismEnvelopeV1) -> tuple[str, ...]:
        o = envelope.proof_obligation
        assert isinstance(o, LimitProofObligationV1)
        errors: list[str] = []
        if envelope.source_domain_root != o.diagram_root or envelope.target_domain_root != o.limit_object_root:
            errors.append("LIMIT_ENDPOINT_BINDING_FAILURE")
        subject = canonical_hash(
            "AEGIS_LIMIT_SUBJECT_V1",
            {
                "diagram_root": o.diagram_root,
                "index_filter_root": o.index_filter_root,
                "topology_root": o.topology_root,
                "limit_object_root": o.limit_object_root,
            },
        )
        err = self._require_proof(
            o.convergence_theorem_receipt_root,
            subject,
            ProofArtifactKind.LIMIT_CONVERGENCE,
            "LIMIT_CONVERGENCE_INVALID",
        )
        if err:
            errors.append(err)
        if o.universal_property_receipt_root:
            err = self._require_proof(
                o.universal_property_receipt_root,
                subject,
                ProofArtifactKind.LIMIT_UNIVERSAL_PROPERTY,
                "LIMIT_UNIVERSAL_PROPERTY_INVALID",
            )
            if err:
                errors.append(err)
        return tuple(sorted(set(errors)))


class SemanticVerifierV1(_ReceiptBackedVerifier):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(kind=MorphismKind.SEMANTIC, **kwargs)

    def verify(self, envelope: MorphismEnvelopeV1) -> tuple[str, ...]:
        o = envelope.proof_obligation
        assert isinstance(o, SemanticProofObligationV1)
        errors: list[str] = []
        if (
            envelope.source_domain_root != o.formal_object_root
            or envelope.target_domain_root != o.target_semantics_root
        ):
            errors.append("SEMANTIC_ENDPOINT_BINDING_FAILURE")
        subject = canonical_hash(
            "AEGIS_SEMANTIC_CORRESPONDENCE_SUBJECT_V1",
            {
                "formal_object_root": o.formal_object_root,
                "target_semantics_root": o.target_semantics_root,
                "convention_root": o.convention_root,
            },
        )
        for root, kind, code in (
            (
                o.soundness_receipt_root,
                ProofArtifactKind.SEMANTIC_SOUNDNESS,
                "SEMANTIC_SOUNDNESS_INVALID",
            ),
            (
                o.correspondence_receipt_root,
                ProofArtifactKind.SEMANTIC_CORRESPONDENCE,
                "SEMANTIC_CORRESPONDENCE_INVALID",
            ),
        ):
            err = self._require_proof(root, subject, kind, code)
            if err:
                errors.append(err)
        if o.completeness_receipt_root:
            err = self._require_proof(
                o.completeness_receipt_root,
                subject,
                ProofArtifactKind.SEMANTIC_COMPLETENESS,
                "SEMANTIC_COMPLETENESS_INVALID",
            )
            if err:
                errors.append(err)
        return tuple(sorted(set(errors)))


class HeritageMorphismVerifierV1:
    kind = MorphismKind.HERITAGE

    def __init__(
        self,
        *,
        verifier_root: str,
        policy_root: str,
        heritage_store: TrustedHeritageReceiptStore,
    ) -> None:
        require_hash("verifier_root", verifier_root)
        require_hash("policy_root", policy_root)
        self.verifier_root = verifier_root
        self.policy_root = policy_root
        self.heritage_store = heritage_store

    def verify(self, envelope: MorphismEnvelopeV1) -> tuple[str, ...]:
        o = envelope.proof_obligation
        assert isinstance(o, HeritageProofObligationV1)
        receipt = self.heritage_store.fetch_verified(o.heritage_receipt_root)
        if receipt is None or receipt.root != o.heritage_receipt_root:
            return ("HERITAGE_RECEIPT_UNTRUSTED",)
        if receipt.envelope_root != o.lineage_envelope_root:
            return ("HERITAGE_RECEIPT_BINDING_FAILURE",)
        if receipt.source_root != envelope.source_domain_root or receipt.derived_root != envelope.target_domain_root:
            return ("HERITAGE_ENDPOINT_BINDING_FAILURE",)
        return ()


class MorphismVerifierRegistryV1:
    def __init__(self, verifiers: tuple[KindVerifier, ...]) -> None:
        by_kind: dict[MorphismKind, KindVerifier] = {}
        for verifier in verifiers:
            if verifier.kind in by_kind:
                raise MorphismError("MORPHISM_VERIFIER_DUPLICATE")
            by_kind[verifier.kind] = verifier
        missing = set(MorphismKind) - set(by_kind)
        if missing:
            raise MorphismError("MORPHISM_VERIFIER_REGISTRY_INCOMPLETE")
        self._verifiers = by_kind

    def verify_and_issue(
        self,
        envelope: MorphismEnvelopeV1,
        *,
        predecessor_receipts: tuple[MorphismReceiptV1, ...] = (),
        receipt_store: TrustedMorphismReceiptStore | None = None,
    ) -> tuple[MorphismVerificationResultV1, MorphismReceiptV1 | None]:
        predecessor_roots: list[str] = []
        errors: list[str] = []
        if predecessor_receipts:
            if receipt_store is None:
                errors.append("MORPHISM_TRUST_STORE_REQUIRED")
            else:
                for receipt in predecessor_receipts:
                    root = receipt.root
                    trusted = receipt_store.fetch_verified(root)
                    if trusted is None or trusted.root != root:
                        errors.append("MORPHISM_PREDECESSOR_UNTRUSTED")
                    predecessor_roots.append(root)

        verifier = self._verifiers[envelope.kind]
        errors.extend(verifier.verify(envelope))
        errors = sorted(set(errors))
        if errors:
            return MorphismVerificationResultV1(DENIED, tuple(errors), None), None

        verification_root = canonical_hash(
            DOM_MORPHISM_VERIFICATION,
            {
                "envelope_root": envelope.root,
                "kind": envelope.kind.value,
                "source_domain_root": envelope.source_domain_root,
                "target_domain_root": envelope.target_domain_root,
                "predecessor_morphism_roots": sorted(predecessor_roots),
                "verifier_root": verifier.verifier_root,
                "policy_root": verifier.policy_root,
                "status": PASS,
                "error_codes": [],
            },
        )
        receipt = MorphismReceiptV1._issue(
            envelope=envelope,
            verification_root=verification_root,
            verifier_root=verifier.verifier_root,
            policy_root=verifier.policy_root,
            predecessor_morphism_roots=tuple(predecessor_roots),
        )
        return MorphismVerificationResultV1(PASS, (), verification_root), receipt

    def compose_and_issue(
        self,
        left: MorphismReceiptV1,
        right: MorphismReceiptV1,
        composed_envelope: MorphismEnvelopeV1,
        *,
        receipt_store: TrustedMorphismReceiptStore,
        composition_store: TrustedCompositionProofStore,
        composition_proof_root: str,
    ) -> tuple[MorphismVerificationResultV1, MorphismReceiptV1 | None]:
        require_hash("composition_proof_root", composition_proof_root)
        if left.target_domain_root != right.source_domain_root:
            return MorphismVerificationResultV1(
                DENIED,
                ("MORPHISM_COMPOSITION_ENDPOINT_MISMATCH",),
                None,
            ), None
        if (
            composed_envelope.source_domain_root != left.source_domain_root
            or composed_envelope.target_domain_root != right.target_domain_root
        ):
            return MorphismVerificationResultV1(
                DENIED,
                ("MORPHISM_COMPOSITION_OUTER_ENDPOINT_MISMATCH",),
                None,
            ), None

        for receipt in (left, right):
            trusted = receipt_store.fetch_verified(receipt.root)
            if trusted is None or trusted.root != receipt.root:
                return MorphismVerificationResultV1(
                    DENIED,
                    ("MORPHISM_PREDECESSOR_UNTRUSTED",),
                    None,
                ), None

        composition_proof = composition_store.fetch_verified(composition_proof_root)
        if composition_proof is None or composition_proof.root != composition_proof_root:
            return MorphismVerificationResultV1(
                DENIED,
                ("MORPHISM_COMPOSITION_PROOF_UNTRUSTED",),
                None,
            ), None
        if (
            composition_proof.left_morphism_root != left.root
            or composition_proof.right_morphism_root != right.root
            or composition_proof.composed_envelope_root != composed_envelope.root
            or composition_proof.midpoint_domain_root != left.target_domain_root
            or composition_proof.midpoint_domain_root != right.source_domain_root
        ):
            return MorphismVerificationResultV1(
                DENIED,
                ("MORPHISM_COMPOSITION_PROOF_BINDING_FAILURE",),
                None,
            ), None

        result, kind_receipt = self.verify_and_issue(
            composed_envelope,
            predecessor_receipts=(left, right),
            receipt_store=receipt_store,
        )
        if kind_receipt is None:
            return result, None

        composition_root = canonical_hash(
            DOM_MORPHISM_COMPOSITION,
            {
                "left_receipt_root": left.root,
                "right_receipt_root": right.root,
                "composed_envelope_root": composed_envelope.root,
                "composition_proof_root": composition_proof.root,
                "interface_contract_root": composition_proof.interface_contract_root,
                "kind_verification_root": kind_receipt.verification_root,
                "status": PASS,
            },
        )
        final_receipt = MorphismReceiptV1._issue(
            envelope=composed_envelope,
            verification_root=composition_root,
            verifier_root=composition_proof.verifier_root,
            policy_root=composition_proof.policy_root,
            predecessor_morphism_roots=(left.root, right.root),
        )
        return MorphismVerificationResultV1(PASS, (), composition_root), final_receipt
