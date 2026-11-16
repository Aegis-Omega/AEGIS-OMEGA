"""Read-only bridge from AEGIS HolonMetadata to MHP-1 semantic lineage.

A repeated byte sequence is the same carrier, NOT the same occurrence or meaning.
This verifier binds a source occurrence to trusted artifacts and MHP receipts;
it does not establish author identity, proposition truth, global holon topology,
semantic equivalence, or execution authority.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol

from harness.sdk.meaning_heritage import (
    ClaimSetReceiptV1,
    HeritageReceiptV1,
    NO_AUTHORITY,
    SemanticLineageEnvelopeV1,
    TrustedClaimSetReceiptStore,
    TrustedHeritageReceiptStore,
    canonical_hash,
    require_hash,
)
from harness.sdk.heritage_composition import TrustedSemanticLineageEnvelopeStore

DOM_HOLON_SNAPSHOT = "AEGIS_HOLON_METADATA_SNAPSHOT_V1"
DOM_SOURCE_OCCURRENCE = "AEGIS_HOLON_SOURCE_OCCURRENCE_V1"
DOM_CONTEXT_BINDING_RECEIPT = "AEGIS_HOLON_CONTEXT_BINDING_RECEIPT_V1"
DOM_HOLON_MEANING_LENS = "AEGIS_HOLON_MEANING_LENS_V1"
DOM_HOLON_MEANING_VERIFICATION = "AEGIS_HOLON_MEANING_VERIFICATION_V1"
DOM_HOLON_MEANING_RECEIPT = "AEGIS_HOLON_MEANING_RECEIPT_V1"

SCALES = frozenset({"subatomic", "atomic", "molecular", "cellular", "organism", "field"})
TIERS = frozenset({"T0", "T1", "T2", "T3", "T4", "T5"})
HOLON_FIELDS = frozenset({
    "holon_id", "scale", "tier", "part_of", "composed_of", "invariants",
    "interaction_surface", "provenance", "ontology_term",
})
PASS = "PASS"
DENIED = "FAIL_HOLON_MEANING_DENIED"


class HolonMeaningError(ValueError):
    pass


def _name(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or not value.strip():
        raise HolonMeaningError(f"{name}:INVALID")
    return value


def _names(name: str, values: object) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise HolonMeaningError(f"{name}:NOT_SEQUENCE")
    result = tuple(_name(name, value) for value in values)
    if len(result) != len(set(result)):
        raise HolonMeaningError(f"{name}:DUPLICATE")
    return result


def _sha(name: str, digest: object) -> str:
    # The existing MHP-1 root validator rejects malformed and uppercase hashes.
    try:
        require_hash(name, digest)
    except (TypeError, ValueError) as exc:
        raise HolonMeaningError(f"{name}:INVALID_SHA256") from exc
    return digest


class TrustedArtifactBytesStore(Protocol):
    """An external evidence store, not a caller-authored hash assertion."""

    def fetch_verified(self, root: str) -> bytes | None: ...


@dataclass(frozen=True)
class HolonSnapshotV1:
    """Exact field projection of sovereign-omega-v2/src/core/types.ts HolonMetadata."""

    holon_id: str
    scale: str
    tier: str
    part_of: tuple[str, ...]
    composed_of: tuple[str, ...]
    invariants: tuple[str, ...]
    interaction_surface: tuple[str, ...]
    provenance: tuple[str, ...]
    ontology_term: str

    def __post_init__(self) -> None:
        _name("holon_id", self.holon_id)
        _name("ontology_term", self.ontology_term)
        if not isinstance(self.scale, str) or self.scale not in SCALES:
            raise HolonMeaningError("HOLON_SCALE_UNKNOWN")
        if not isinstance(self.tier, str) or self.tier not in TIERS:
            raise HolonMeaningError("HOLON_TIER_UNKNOWN")
        for key in ("part_of", "composed_of", "invariants", "interaction_surface", "provenance"):
            if not isinstance(getattr(self, key), tuple):
                raise HolonMeaningError(f"{key}:NOT_TUPLE")
            _names(key, getattr(self, key))
        if self.holon_id in self.part_of or self.holon_id in self.composed_of:
            raise HolonMeaningError("HOLON_SELF_EDGE")
        if set(self.part_of) & set(self.composed_of):
            raise HolonMeaningError("HOLON_PARENT_CHILD_OVERLAP")
        if self.tier in {"T0", "T1", "T2"} and not self.provenance:
            raise HolonMeaningError("HOLON_PROVENANCE_REQUIRED")

    @classmethod
    def from_typescript_record(cls, record: Mapping[str, Any]) -> HolonSnapshotV1:
        if not isinstance(record, Mapping) or set(record) != HOLON_FIELDS:
            raise HolonMeaningError("HOLON_METADATA_SHAPE_INVALID")
        return cls(
            holon_id=_name("holon_id", record["holon_id"]),
            scale=record["scale"], tier=record["tier"],
            part_of=_names("part_of", record["part_of"]),
            composed_of=_names("composed_of", record["composed_of"]),
            invariants=_names("invariants", record["invariants"]),
            interaction_surface=_names("interaction_surface", record["interaction_surface"]),
            provenance=_names("provenance", record["provenance"]),
            ontology_term=_name("ontology_term", record["ontology_term"]),
        )

    @property
    def root(self) -> str:
        return canonical_hash(DOM_HOLON_SNAPSHOT, asdict(self))


@dataclass(frozen=True)
class SourceOccurrenceV1:
    """A byte interval in a separately authenticated parent artifact."""

    artifact_root: str
    start_byte: int
    end_byte: int
    carrier_root: str

    def __post_init__(self) -> None:
        _sha("artifact_root", self.artifact_root)
        _sha("carrier_root", self.carrier_root)
        if (isinstance(self.start_byte, bool) or isinstance(self.end_byte, bool)
                or not isinstance(self.start_byte, int) or not isinstance(self.end_byte, int)
                or self.start_byte < 0 or self.end_byte <= self.start_byte):
            raise HolonMeaningError("SOURCE_SPAN_INVALID")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_SOURCE_OCCURRENCE, asdict(self))


@dataclass(frozen=True)
class ContextualReadingV1:
    """One candidate meaning and its existing independently verified MHP lineage."""

    reading_id: str
    context_root: str
    envelope_root: str
    heritage_receipt_root: str
    context_binding_receipt_root: str

    def __post_init__(self) -> None:
        _name("reading_id", self.reading_id)
        for key in ("context_root", "envelope_root", "heritage_receipt_root", "context_binding_receipt_root"):
            _sha(key, getattr(self, key))


@dataclass(frozen=True)
class ContextBindingReceiptV1:
    """Verified external binding of holon, source occurrence, context and MHP transform.

    The object is evidence only. Its mere construction does not establish trust;
    the bridge requires readback from an independent trusted receipt store.
    """

    reading_id: str
    holon_root: str
    occurrence_root: str
    context_root: str
    envelope_root: str
    transform_root: str
    derived_root: str
    verifier_root: str
    policy_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-context-binding-receipt.v1", init=False)

    def __post_init__(self) -> None:
        _name("reading_id", self.reading_id)
        for key in ("holon_root", "occurrence_root", "context_root", "envelope_root", "transform_root", "derived_root", "verifier_root", "policy_root"):
            _sha(key, getattr(self, key))

    @property
    def root(self) -> str:
        return canonical_hash(DOM_CONTEXT_BINDING_RECEIPT, asdict(self))


class TrustedContextBindingReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> ContextBindingReceiptV1 | None: ...


@dataclass(frozen=True)
class HolonMeaningLensV1:
    holon: HolonSnapshotV1
    occurrence: SourceOccurrenceV1
    readings: tuple[ContextualReadingV1, ...]
    schema_version: str = field(default="aegis.holon-meaning-lens.v1", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.holon, HolonSnapshotV1) or not isinstance(self.occurrence, SourceOccurrenceV1):
            raise HolonMeaningError("HOLON_LENS_COMPONENT_INVALID")
        if not isinstance(self.readings, tuple) or not self.readings:
            raise HolonMeaningError("HOLON_READINGS_REQUIRED")
        if any(not isinstance(r, ContextualReadingV1) for r in self.readings):
            raise HolonMeaningError("HOLON_READING_INVALID")
        if len({r.reading_id for r in self.readings}) != len(self.readings):
            raise HolonMeaningError("HOLON_READING_ID_DUPLICATE")
        if len({(r.context_root, r.envelope_root, r.heritage_receipt_root, r.context_binding_receipt_root) for r in self.readings}) != len(self.readings):
            raise HolonMeaningError("HOLON_READING_PROOF_DUPLICATE")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_HOLON_MEANING_LENS, {
            "schema_version": self.schema_version,
            "holon_root": self.holon.root,
            "occurrence_root": self.occurrence.root,
            "readings": sorted((asdict(r) for r in self.readings), key=lambda r: r["reading_id"]),
        })


@dataclass(frozen=True)
class HolonMeaningVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class HolonMeaningReceiptV1:
    lens_root: str
    occurrence_root: str
    holon_root: str
    heritage_receipt_roots: tuple[str, ...]
    context_binding_receipt_roots: tuple[str, ...]
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-meaning-receipt.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_HOLON_MEANING_RECEIPT, asdict(self))


class HolonMeaningVerifierV1:
    """Evidence-only verifier; every artifact and prior MHP receipt must be trusted."""

    def __init__(self, *, artifacts: TrustedArtifactBytesStore,
                 heritage: TrustedHeritageReceiptStore,
                 envelopes: TrustedSemanticLineageEnvelopeStore,
                 claimsets: TrustedClaimSetReceiptStore,
                 context_bindings: TrustedContextBindingReceiptStore):
        self.artifacts = artifacts
        self.heritage = heritage
        self.envelopes = envelopes
        self.claimsets = claimsets
        self.context_bindings = context_bindings

    def verify(self, lens: HolonMeaningLensV1) -> tuple[HolonMeaningVerificationV1, HolonMeaningReceiptV1 | None]:
        def deny(code: str):
            return HolonMeaningVerificationV1(DENIED, (code,), None), None

        # The original is not replaced with its token: authenticate parent bytes AND span.
        source = self.artifacts.fetch_verified(lens.occurrence.artifact_root)
        if (not isinstance(source, bytes)
                or hashlib.sha256(source).hexdigest() != lens.occurrence.artifact_root):
            return deny("SOURCE_ARTIFACT_UNTRUSTED")
        if lens.occurrence.end_byte > len(source):
            return deny("SOURCE_SPAN_OUT_OF_BOUNDS")
        selected = source[lens.occurrence.start_byte:lens.occurrence.end_byte]
        if hashlib.sha256(selected).hexdigest() != lens.occurrence.carrier_root:
            return deny("SOURCE_SPAN_CARRIER_MISMATCH")

        for reading in lens.readings:
            context = self.artifacts.fetch_verified(reading.context_root)
            if (not isinstance(context, bytes) or not context
                    or hashlib.sha256(context).hexdigest() != reading.context_root):
                return deny("READING_CONTEXT_UNTRUSTED")
            envelope = self.envelopes.fetch_verified(reading.envelope_root)
            receipt = self.heritage.fetch_verified(reading.heritage_receipt_root)
            if (not isinstance(envelope, SemanticLineageEnvelopeV1)
                    or envelope.root != reading.envelope_root):
                return deny("READING_ENVELOPE_UNTRUSTED")
            if (not isinstance(receipt, HeritageReceiptV1)
                    or receipt.root != reading.heritage_receipt_root
                    or receipt.authority_class != NO_AUTHORITY
                    or not receipt.loss_certified):
                return deny("READING_HERITAGE_UNTRUSTED")
            context_binding = self.context_bindings.fetch_verified(reading.context_binding_receipt_root)
            if (not isinstance(context_binding, ContextBindingReceiptV1)
                    or context_binding.root != reading.context_binding_receipt_root
                    or context_binding.authority_class != NO_AUTHORITY):
                return deny("READING_CONTEXT_BINDING_UNTRUSTED")
            if (context_binding.reading_id != reading.reading_id
                    or context_binding.holon_root != lens.holon.root
                    or context_binding.occurrence_root != lens.occurrence.root
                    or context_binding.context_root != reading.context_root
                    or context_binding.envelope_root != envelope.root
                    or context_binding.transform_root != envelope.transform_root
                    or context_binding.derived_root != envelope.derived_root):
                return deny("READING_CONTEXT_TRANSPLANT")
            if (receipt.envelope_root != envelope.root
                    or receipt.source_root != lens.occurrence.carrier_root
                    or envelope.source_root != lens.occurrence.carrier_root
                    or receipt.source_claimset_receipt_root != envelope.source_claimset_receipt_root
                    or receipt.derived_root != envelope.derived_root
                    or receipt.derived_claimset_receipt_root != envelope.derived_claimset_receipt_root
                    or receipt.transform_root != envelope.transform_root):
                return deny("READING_MHP_BINDING_MISMATCH")
            for root, payload_root in (
                (receipt.source_claimset_receipt_root, lens.occurrence.carrier_root),
                (receipt.derived_claimset_receipt_root, envelope.derived_root),
            ):
                claimset = self.claimsets.fetch_verified(root)
                if (not isinstance(claimset, ClaimSetReceiptV1)
                        or claimset.root != root or claimset.payload_root != payload_root):
                    return deny("READING_CLAIMSET_UNTRUSTED")
            derived = self.artifacts.fetch_verified(envelope.derived_root)
            if (not isinstance(derived, bytes)
                    or hashlib.sha256(derived).hexdigest() != envelope.derived_root):
                return deny("READING_DERIVED_ARTIFACT_UNTRUSTED")

        refs = tuple(sorted(r.heritage_receipt_root for r in lens.readings))
        context_refs = tuple(sorted(r.context_binding_receipt_root for r in lens.readings))
        verification_root = canonical_hash(DOM_HOLON_MEANING_VERIFICATION, {
            "lens_root": lens.root,
            "holon_root": lens.holon.root,
            "occurrence_root": lens.occurrence.root,
            "heritage_receipt_roots": refs,
            "context_binding_receipt_roots": context_refs,
            "status": PASS,
        })
        receipt = HolonMeaningReceiptV1(lens.root, lens.occurrence.root, lens.holon.root, refs, context_refs, verification_root)
        return HolonMeaningVerificationV1(PASS, (), verification_root), receipt
