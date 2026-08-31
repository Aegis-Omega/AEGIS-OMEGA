"""AEGIS MHP-1 Meaning Heritage kernel v1.3.

Evidence-only semantic-lineage verification. This module never grants execution,
admission, or canonical authority. All roots use the repository-local canonical
hash primitive and all successful receipts remain authority_class == "NONE".
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Protocol

from harness.sdk.sovereign_execution import canonical_hash

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

DOM_CLAIMSET_ENVELOPE = "AEGIS_MHP1_CLAIMSET_ENVELOPE_V1"
DOM_CLAIMSET_VERIFICATION = "AEGIS_MHP1_CLAIMSET_VERIFICATION_V1"
DOM_CLAIMSET_RECEIPT = "AEGIS_MHP1_CLAIMSET_RECEIPT_V1"
DOM_PRESERVATION_PROOF = "AEGIS_MHP1_PRESERVATION_PROOF_V1"
DOM_DERIVATION_PROOF = "AEGIS_MHP1_DERIVATION_PROOF_V1"
DOM_LINEAGE = "AEGIS_MHP1_LINEAGE_V1"
DOM_HERITAGE_VERIFICATION = "AEGIS_MHP1_HERITAGE_VERIFICATION_V1"
DOM_HERITAGE_RECEIPT = "AEGIS_MHP1_HERITAGE_RECEIPT_V1"

NO_AUTHORITY = "NONE"
PASS = "PASS"
DENIED = "FAIL_HERITAGE_DENIED"


class HeritageError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise HeritageError(f"{name}:MALFORMED_ROOT")


def require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise HeritageError(f"{name}:INVALID_ID")


def _require_unique(name: str, values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        raise HeritageError(f"{name}:DUPLICATE")


class TransformRelation(str, Enum):
    IDENTITY = "IDENTITY"
    LOSSLESS_TRANSFORM = "LOSSLESS_TRANSFORM"
    LOSSY_TRANSFORM = "LOSSY_TRANSFORM"
    AUGMENTING_TRANSFORM = "AUGMENTING_TRANSFORM"


class LossType(str, Enum):
    EXACT_LOSSLESS = "EXACT_LOSSLESS"
    PRECISION_TRUNCATION = "PRECISION_TRUNCATION"
    STRUCTURAL_PROJECTION = "STRUCTURAL_PROJECTION"
    LOSS_BY_SUMMARIZATION = "LOSS_BY_SUMMARIZATION"
    HEURISTIC_ABSTRACTION = "HEURISTIC_ABSTRACTION"


class PreservationRelation(str, Enum):
    SAME_CLAIM_ROOT = "SAME_CLAIM_ROOT"
    SEMANTIC_EQUIVALENCE = "SEMANTIC_EQUIVALENCE"
    PARAPHRASE_ABSTRACTION = "PARAPHRASE_ABSTRACTION"


class VerificationErrorCode(str, Enum):
    CLAIMSET_EXTRACTION_MISMATCH = "CLAIMSET_EXTRACTION_MISMATCH"
    DUPLICATE_CLAIM_DIGEST = "DUPLICATE_CLAIM_DIGEST"
    CLAIMSET_SOURCE_BINDING_FAILURE = "CLAIMSET_SOURCE_BINDING_FAILURE"
    CLAIMSET_DERIVED_BINDING_FAILURE = "CLAIMSET_DERIVED_BINDING_FAILURE"
    CLAIMSET_TRUST_STORE_REQUIRED = "CLAIMSET_TRUST_STORE_REQUIRED"
    CLAIMSET_RECEIPT_UNTRUSTED = "CLAIMSET_RECEIPT_UNTRUSTED"
    UNDECLARED_LOSS = "UNDECLARED_LOSS"
    UNDECLARED_ADDITION = "UNDECLARED_ADDITION"
    PRESERVATION_PROOF_UNTRUSTED = "PRESERVATION_PROOF_UNTRUSTED"
    PRESERVATION_PROOF_BINDING_FAILURE = "PRESERVATION_PROOF_BINDING_FAILURE"
    PRESERVATION_PROOF_FINGERPRINT_MISMATCH = "PRESERVATION_PROOF_FINGERPRINT_MISMATCH"
    DERIVATION_PROOF_UNTRUSTED = "DERIVATION_PROOF_UNTRUSTED"
    DERIVATION_PROOF_BINDING_FAILURE = "DERIVATION_PROOF_BINDING_FAILURE"
    DERIVATION_PROOF_FINGERPRINT_MISMATCH = "DERIVATION_PROOF_FINGERPRINT_MISMATCH"
    LOSS_CONTRACT_INCONSISTENT = "LOSS_CONTRACT_INCONSISTENT"
    TRUST_STORE_REQUIRED = "TRUST_STORE_REQUIRED"
    PREDECESSOR_RECEIPT_INVALID = "PREDECESSOR_RECEIPT_INVALID"
    COMPOSITION_ENDPOINT_MISMATCH = "COMPOSITION_ENDPOINT_MISMATCH"


@dataclass(frozen=True)
class ClaimRef:
    claim_id: str
    claim_digest: str
    semantic_fingerprint: str

    def __post_init__(self) -> None:
        require_id("claim_id", self.claim_id)
        require_hash("claim_digest", self.claim_digest)
        require_id("semantic_fingerprint", self.semantic_fingerprint)


class ClaimExtractorV1(Protocol):
    extractor_root: str
    policy_root: str

    def extract(self, payload: bytes) -> tuple[ClaimRef, ...]: ...


def canonicalize_claims(claims: tuple[ClaimRef, ...]) -> tuple[ClaimRef, ...]:
    digests = tuple(c.claim_digest for c in claims)
    if len(digests) != len(set(digests)):
        raise HeritageError(VerificationErrorCode.DUPLICATE_CLAIM_DIGEST.value)
    return tuple(sorted(claims, key=lambda c: c.claim_digest))


@dataclass(frozen=True)
class ClaimSetEnvelopeV1:
    lineage_id: str
    payload_root: str
    raw_claims: tuple[ClaimRef, ...]
    extractor_root: str
    extractor_policy_root: str
    schema_version: str = "aegis.claimset-envelope.v1"

    def __post_init__(self) -> None:
        require_id("lineage_id", self.lineage_id)
        require_hash("payload_root", self.payload_root)
        require_hash("extractor_root", self.extractor_root)
        require_hash("extractor_policy_root", self.extractor_policy_root)
        canonicalize_claims(self.raw_claims)

    @property
    def root(self) -> str:
        payload = asdict(self)
        payload["raw_claims"] = [asdict(c) for c in canonicalize_claims(self.raw_claims)]
        return canonical_hash(DOM_CLAIMSET_ENVELOPE, payload)


@dataclass(frozen=True)
class ClaimSetReceiptV1:
    claimset_envelope_root: str
    payload_root: str
    extractor_root: str
    extractor_policy_root: str
    claimset_root: str
    sorted_claims: tuple[ClaimRef, ...]
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.claimset-receipt.v1"

    def __post_init__(self) -> None:
        for name in (
            "claimset_envelope_root",
            "payload_root",
            "extractor_root",
            "extractor_policy_root",
            "claimset_root",
            "verification_root",
        ):
            require_hash(name, getattr(self, name))
        canonical = canonicalize_claims(self.sorted_claims)
        if self.sorted_claims != canonical:
            raise HeritageError("CLAIMSET_ORDER_NONCANONICAL")

    @property
    def sorted_claim_digests(self) -> tuple[str, ...]:
        return tuple(claim.claim_digest for claim in self.sorted_claims)

    @property
    def claim_map(self) -> dict[str, ClaimRef]:
        return {claim.claim_digest: claim for claim in self.sorted_claims}

    @property
    def root(self) -> str:
        data = asdict(self)
        data["sorted_claims"] = [asdict(c) for c in self.sorted_claims]
        return canonical_hash(DOM_CLAIMSET_RECEIPT, data)


class ClaimSetVerifierV13:
    @staticmethod
    def verify_and_issue(
        envelope: ClaimSetEnvelopeV1,
        actual_payload_bytes: bytes,
        extractor: ClaimExtractorV1,
    ) -> ClaimSetReceiptV1:
        payload_root = hashlib.sha256(actual_payload_bytes).hexdigest()
        if payload_root != envelope.payload_root:
            raise HeritageError("CLAIMSET_PAYLOAD_ROOT_MISMATCH")
        require_hash("extractor.extractor_root", extractor.extractor_root)
        require_hash("extractor.policy_root", extractor.policy_root)
        if (
            extractor.extractor_root != envelope.extractor_root
            or extractor.policy_root != envelope.extractor_policy_root
        ):
            raise HeritageError(VerificationErrorCode.CLAIMSET_EXTRACTION_MISMATCH.value)

        declared = canonicalize_claims(envelope.raw_claims)
        recomputed = canonicalize_claims(extractor.extract(actual_payload_bytes))
        if declared != recomputed:
            raise HeritageError(VerificationErrorCode.CLAIMSET_EXTRACTION_MISMATCH.value)

        claimset_payload = [asdict(c) for c in recomputed]
        claimset_root = canonical_hash("AEGIS_MHP1_CLAIMSET_V1", claimset_payload)
        verification_root = canonical_hash(
            DOM_CLAIMSET_VERIFICATION,
            {
                "claimset_envelope_root": envelope.root,
                "payload_root": payload_root,
                "extractor_root": extractor.extractor_root,
                "extractor_policy_root": extractor.policy_root,
                "claimset_root": claimset_root,
                "status": PASS,
            },
        )
        return ClaimSetReceiptV1(
            claimset_envelope_root=envelope.root,
            payload_root=payload_root,
            extractor_root=extractor.extractor_root,
            extractor_policy_root=extractor.policy_root,
            claimset_root=claimset_root,
            sorted_claims=recomputed,
            verification_root=verification_root,
        )


class TrustedClaimSetReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> ClaimSetReceiptV1 | None: ...


@dataclass(frozen=True)
class PreservationProofReceiptV1:
    source_claim_digest: str
    derived_claim_digest: str
    relation: PreservationRelation
    source_semantic_fingerprint: str
    derived_semantic_fingerprint: str
    verifier_root: str
    policy_root: str
    status: str = PASS
    authority_class: str = field(default=NO_AUTHORITY, init=False)

    def __post_init__(self) -> None:
        require_hash("source_claim_digest", self.source_claim_digest)
        require_hash("derived_claim_digest", self.derived_claim_digest)
        require_id("source_semantic_fingerprint", self.source_semantic_fingerprint)
        require_id("derived_semantic_fingerprint", self.derived_semantic_fingerprint)
        require_hash("verifier_root", self.verifier_root)
        require_hash("policy_root", self.policy_root)
        if self.status != PASS:
            raise HeritageError("PRESERVATION_PROOF_NOT_PASS")
        if (
            self.relation == PreservationRelation.SAME_CLAIM_ROOT
            and self.source_claim_digest != self.derived_claim_digest
        ):
            raise HeritageError("SAME_CLAIM_ROOT_MISMATCH")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["relation"] = self.relation.value
        return canonical_hash(DOM_PRESERVATION_PROOF, data)


@dataclass(frozen=True)
class DerivationProofReceiptV1:
    derived_claim_digest: str
    source_claim_digests: tuple[str, ...]
    source_semantic_fingerprints: tuple[str, ...]
    derived_semantic_fingerprint: str
    transform_root: str
    verifier_root: str
    policy_root: str
    status: str = PASS
    authority_class: str = field(default=NO_AUTHORITY, init=False)

    def __post_init__(self) -> None:
        require_hash("derived_claim_digest", self.derived_claim_digest)
        for digest in self.source_claim_digests:
            require_hash("source_claim_digest", digest)
        _require_unique("source_claim_digests", self.source_claim_digests)
        if len(self.source_semantic_fingerprints) != len(self.source_claim_digests):
            raise HeritageError("DERIVATION_SOURCE_FINGERPRINT_ARITY_MISMATCH")
        for fingerprint in self.source_semantic_fingerprints:
            require_id("source_semantic_fingerprint", fingerprint)
        require_id("derived_semantic_fingerprint", self.derived_semantic_fingerprint)
        require_hash("transform_root", self.transform_root)
        require_hash("verifier_root", self.verifier_root)
        require_hash("policy_root", self.policy_root)
        if self.status != PASS:
            raise HeritageError("DERIVATION_PROOF_NOT_PASS")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_DERIVATION_PROOF, asdict(self))


class TrustedSemanticProofStore(Protocol):
    def fetch_preservation(self, root: str) -> PreservationProofReceiptV1 | None: ...

    def fetch_derivation(self, root: str) -> DerivationProofReceiptV1 | None: ...


class TrustedHeritageReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> "HeritageReceiptV1 | None": ...


@dataclass(frozen=True)
class PreservationEdge:
    source_claim_digest: str
    derived_claim_digest: str
    relation: PreservationRelation
    proof_receipt_root: str

    def __post_init__(self) -> None:
        require_hash("source_claim_digest", self.source_claim_digest)
        require_hash("derived_claim_digest", self.derived_claim_digest)
        require_hash("proof_receipt_root", self.proof_receipt_root)


@dataclass(frozen=True)
class DeclaredAdditionEdge:
    derived_claim_digest: str
    derivation_receipt_root: str

    def __post_init__(self) -> None:
        require_hash("derived_claim_digest", self.derived_claim_digest)
        require_hash("derivation_receipt_root", self.derivation_receipt_root)


@dataclass(frozen=True)
class SemanticLineageEnvelopeV1:
    lineage_id: str
    source_root: str
    source_claimset_receipt_root: str
    derived_root: str
    derived_claimset_receipt_root: str
    transform_root: str
    transform_relation: TransformRelation
    loss_type: LossType
    preservation_edges: tuple[PreservationEdge, ...]
    declared_omission_digests: tuple[str, ...]
    declared_additions: tuple[DeclaredAdditionEdge, ...]
    uncertainty_bps: int
    schema_version: str = "aegis.semantic-lineage-envelope.v1"

    def __post_init__(self) -> None:
        require_id("lineage_id", self.lineage_id)
        for name in (
            "source_root",
            "source_claimset_receipt_root",
            "derived_root",
            "derived_claimset_receipt_root",
            "transform_root",
        ):
            require_hash(name, getattr(self, name))
        for digest in self.declared_omission_digests:
            require_hash("declared_omission_digest", digest)
        _require_unique("declared_omission_digests", self.declared_omission_digests)
        edge_keys = tuple(
            (edge.source_claim_digest, edge.derived_claim_digest, edge.relation.value)
            for edge in self.preservation_edges
        )
        if len(edge_keys) != len(set(edge_keys)):
            raise HeritageError("PRESERVATION_EDGE_DUPLICATE")
        addition_keys = tuple(addition.derived_claim_digest for addition in self.declared_additions)
        _require_unique("declared_additions", addition_keys)
        if (
            isinstance(self.uncertainty_bps, bool)
            or not isinstance(self.uncertainty_bps, int)
            or not 0 <= self.uncertainty_bps <= 10000
        ):
            raise HeritageError("UNCERTAINTY_BPS_INVALID")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["transform_relation"] = self.transform_relation.value
        data["loss_type"] = self.loss_type.value
        data["preservation_edges"] = sorted(
            [
                {
                    "source_claim_digest": edge.source_claim_digest,
                    "derived_claim_digest": edge.derived_claim_digest,
                    "relation": edge.relation.value,
                    "proof_receipt_root": edge.proof_receipt_root,
                }
                for edge in self.preservation_edges
            ],
            key=lambda item: (
                item["source_claim_digest"],
                item["derived_claim_digest"],
                item["relation"],
            ),
        )
        data["declared_omission_digests"] = sorted(self.declared_omission_digests)
        data["declared_additions"] = sorted(
            [asdict(addition) for addition in self.declared_additions],
            key=lambda item: item["derived_claim_digest"],
        )
        return canonical_hash(DOM_LINEAGE, data)


@dataclass(frozen=True)
class HeritageVerificationResultV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None

    def __post_init__(self) -> None:
        if self.status not in {PASS, DENIED}:
            raise HeritageError("HERITAGE_STATUS_INVALID")
        if self.verification_root is not None:
            require_hash("verification_root", self.verification_root)


@dataclass(frozen=True)
class HeritageReceiptV1:
    envelope_root: str
    source_root: str
    source_claimset_receipt_root: str
    derived_root: str
    derived_claimset_receipt_root: str
    transform_root: str
    verification_root: str
    loss_certified: bool
    predecessor_receipt_roots: tuple[str, ...]
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = "aegis.heritage-receipt.v1"

    def __post_init__(self) -> None:
        for name in (
            "envelope_root",
            "source_root",
            "source_claimset_receipt_root",
            "derived_root",
            "derived_claimset_receipt_root",
            "transform_root",
            "verification_root",
        ):
            require_hash(name, getattr(self, name))
        for root in self.predecessor_receipt_roots:
            require_hash("predecessor_receipt_root", root)
        _require_unique("predecessor_receipt_roots", self.predecessor_receipt_roots)
        if not self.loss_certified:
            raise HeritageError("HERITAGE_RECEIPT_MUST_CERTIFY_LOSS")

    @property
    def root(self) -> str:
        data = asdict(self)
        data["predecessor_receipt_roots"] = sorted(self.predecessor_receipt_roots)
        return canonical_hash(DOM_HERITAGE_RECEIPT, data)


class HeritageVerifierV13:
    def __init__(
        self,
        *,
        verifier_root: str,
        policy_root: str,
        proof_store: TrustedSemanticProofStore,
        claimset_store: TrustedClaimSetReceiptStore | None = None,
        heritage_store: TrustedHeritageReceiptStore | None = None,
    ) -> None:
        require_hash("verifier_root", verifier_root)
        require_hash("policy_root", policy_root)
        self.verifier_root = verifier_root
        self.policy_root = policy_root
        self.proof_store = proof_store
        self.claimset_store = claimset_store
        self.heritage_store = heritage_store

    def verify(
        self,
        envelope: SemanticLineageEnvelopeV1,
        source_claimset: ClaimSetReceiptV1,
        derived_claimset: ClaimSetReceiptV1,
        predecessor_receipts: tuple[HeritageReceiptV1, ...] = (),
    ) -> tuple[HeritageVerificationResultV1, HeritageReceiptV1 | None]:
        errors: list[str] = []
        if self.claimset_store is None:
            errors.append(VerificationErrorCode.CLAIMSET_TRUST_STORE_REQUIRED.value)
            errors.append(VerificationErrorCode.CLAIMSET_RECEIPT_UNTRUSTED.value)
        else:
            for claimset in (source_claimset, derived_claimset):
                trusted = self.claimset_store.fetch_verified(claimset.root)
                if trusted is None or trusted != claimset or trusted.root != claimset.root:
                    errors.append(VerificationErrorCode.CLAIMSET_RECEIPT_UNTRUSTED.value)

        if (
            source_claimset.root != envelope.source_claimset_receipt_root
            or source_claimset.payload_root != envelope.source_root
        ):
            errors.append(VerificationErrorCode.CLAIMSET_SOURCE_BINDING_FAILURE.value)
        if (
            derived_claimset.root != envelope.derived_claimset_receipt_root
            or derived_claimset.payload_root != envelope.derived_root
        ):
            errors.append(VerificationErrorCode.CLAIMSET_DERIVED_BINDING_FAILURE.value)

        src_map = source_claimset.claim_map
        der_map = derived_claimset.claim_map
        src = set(src_map)
        der = set(der_map)
        preserved_src: set[str] = set()
        preserved_der: set[str] = set()

        for edge in envelope.preservation_edges:
            preserved_src.add(edge.source_claim_digest)
            preserved_der.add(edge.derived_claim_digest)
            proof = self.proof_store.fetch_preservation(edge.proof_receipt_root)
            if proof is None or proof.root != edge.proof_receipt_root:
                errors.append(VerificationErrorCode.PRESERVATION_PROOF_UNTRUSTED.value)
                continue
            if (
                proof.source_claim_digest != edge.source_claim_digest
                or proof.derived_claim_digest != edge.derived_claim_digest
                or proof.relation != edge.relation
            ):
                errors.append(VerificationErrorCode.PRESERVATION_PROOF_BINDING_FAILURE.value)
            source_claim = src_map.get(edge.source_claim_digest)
            derived_claim = der_map.get(edge.derived_claim_digest)
            if source_claim is None or derived_claim is None:
                errors.append(VerificationErrorCode.PRESERVATION_PROOF_BINDING_FAILURE.value)
                continue
            if (
                proof.source_semantic_fingerprint != source_claim.semantic_fingerprint
                or proof.derived_semantic_fingerprint != derived_claim.semantic_fingerprint
            ):
                errors.append(
                    VerificationErrorCode.PRESERVATION_PROOF_FINGERPRINT_MISMATCH.value
                )

        omissions = set(envelope.declared_omission_digests)
        if src - (preserved_src | omissions):
            errors.append(VerificationErrorCode.UNDECLARED_LOSS.value)

        additions: set[str] = set()
        for addition in envelope.declared_additions:
            additions.add(addition.derived_claim_digest)
            proof = self.proof_store.fetch_derivation(addition.derivation_receipt_root)
            if proof is None or proof.root != addition.derivation_receipt_root:
                errors.append(VerificationErrorCode.DERIVATION_PROOF_UNTRUSTED.value)
                continue
            if (
                proof.derived_claim_digest != addition.derived_claim_digest
                or proof.transform_root != envelope.transform_root
            ):
                errors.append(VerificationErrorCode.DERIVATION_PROOF_BINDING_FAILURE.value)
            source_claims = [src_map.get(digest) for digest in proof.source_claim_digests]
            derived_claim = der_map.get(addition.derived_claim_digest)
            if not set(proof.source_claim_digests).issubset(src):
                errors.append(VerificationErrorCode.DERIVATION_PROOF_BINDING_FAILURE.value)
            if derived_claim is None or any(claim is None for claim in source_claims):
                errors.append(VerificationErrorCode.DERIVATION_PROOF_BINDING_FAILURE.value)
            else:
                authenticated_source_fingerprints = tuple(
                    claim.semantic_fingerprint
                    for claim in source_claims
                    if claim is not None
                )
                if (
                    proof.source_semantic_fingerprints
                    != authenticated_source_fingerprints
                    or proof.derived_semantic_fingerprint
                    != derived_claim.semantic_fingerprint
                ):
                    errors.append(
                        VerificationErrorCode.DERIVATION_PROOF_FINGERPRINT_MISMATCH.value
                    )

        if der - (preserved_der | additions):
            errors.append(VerificationErrorCode.UNDECLARED_ADDITION.value)

        if envelope.transform_relation == TransformRelation.IDENTITY:
            if (
                envelope.source_root != envelope.derived_root
                or envelope.source_claimset_receipt_root
                != envelope.derived_claimset_receipt_root
                or envelope.loss_type != LossType.EXACT_LOSSLESS
                or omissions
                or additions
                or envelope.uncertainty_bps != 0
            ):
                errors.append(VerificationErrorCode.LOSS_CONTRACT_INCONSISTENT.value)
        elif envelope.transform_relation == TransformRelation.LOSSLESS_TRANSFORM:
            if (
                envelope.loss_type != LossType.EXACT_LOSSLESS
                or omissions
                or additions
                or envelope.uncertainty_bps != 0
            ):
                errors.append(VerificationErrorCode.LOSS_CONTRACT_INCONSISTENT.value)
        elif envelope.transform_relation == TransformRelation.LOSSY_TRANSFORM:
            if envelope.loss_type == LossType.EXACT_LOSSLESS:
                errors.append(VerificationErrorCode.LOSS_CONTRACT_INCONSISTENT.value)
        elif envelope.transform_relation == TransformRelation.AUGMENTING_TRANSFORM:
            if (
                omissions
                or envelope.loss_type != LossType.EXACT_LOSSLESS
                or envelope.uncertainty_bps != 0
            ):
                errors.append(VerificationErrorCode.LOSS_CONTRACT_INCONSISTENT.value)

        predecessor_roots: list[str] = []
        if predecessor_receipts:
            if self.heritage_store is None:
                errors.append(VerificationErrorCode.TRUST_STORE_REQUIRED.value)
            else:
                for predecessor in predecessor_receipts:
                    root = predecessor.root
                    trusted = self.heritage_store.fetch_verified(root)
                    if trusted is None or trusted.root != root:
                        errors.append(VerificationErrorCode.PREDECESSOR_RECEIPT_INVALID.value)
                    predecessor_roots.append(root)

        if errors:
            return (
                HeritageVerificationResultV1(
                    DENIED,
                    tuple(sorted(set(errors))),
                    None,
                ),
                None,
            )

        verification_root = canonical_hash(
            DOM_HERITAGE_VERIFICATION,
            {
                "envelope_root": envelope.root,
                "source_claimset_receipt_root": source_claimset.root,
                "derived_claimset_receipt_root": derived_claimset.root,
                "predecessor_receipt_roots": sorted(predecessor_roots),
                "verifier_root": self.verifier_root,
                "policy_root": self.policy_root,
                "status": PASS,
                "error_codes": [],
            },
        )
        receipt = HeritageReceiptV1(
            envelope_root=envelope.root,
            source_root=envelope.source_root,
            source_claimset_receipt_root=envelope.source_claimset_receipt_root,
            derived_root=envelope.derived_root,
            derived_claimset_receipt_root=envelope.derived_claimset_receipt_root,
            transform_root=envelope.transform_root,
            verification_root=verification_root,
            loss_certified=True,
            predecessor_receipt_roots=tuple(sorted(predecessor_roots)),
        )
        return HeritageVerificationResultV1(PASS, (), verification_root), receipt

    def compose(
        self,
        h1: HeritageReceiptV1,
        h2: HeritageReceiptV1,
        composed_envelope: SemanticLineageEnvelopeV1,
        source_claimset: ClaimSetReceiptV1,
        derived_claimset: ClaimSetReceiptV1,
    ) -> tuple[HeritageVerificationResultV1, HeritageReceiptV1 | None]:
        if (
            h1.derived_root != h2.source_root
            or h1.derived_claimset_receipt_root != h2.source_claimset_receipt_root
            or composed_envelope.source_root != h1.source_root
            or composed_envelope.source_claimset_receipt_root
            != h1.source_claimset_receipt_root
            or composed_envelope.derived_root != h2.derived_root
            or composed_envelope.derived_claimset_receipt_root
            != h2.derived_claimset_receipt_root
        ):
            return (
                HeritageVerificationResultV1(
                    DENIED,
                    (VerificationErrorCode.COMPOSITION_ENDPOINT_MISMATCH.value,),
                    None,
                ),
                None,
            )
        return self.verify(
            composed_envelope,
            source_claimset,
            derived_claimset,
            (h1, h2),
        )
