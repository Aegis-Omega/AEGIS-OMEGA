"""Proof-bound, context-specific support for finite AEGIS meaning relations.

Existing MHP-1 verifies the origin and lineage of readings; the existing
MorphismVerifierRegistryV1 verifies *typed and externally proof-backed* semantic
correspondence morphisms. This bridge requires one independently retrievable
semantic morphism per allowed context-reading pair and binds its proof
convention to the exact MHP lens, context binding receipts, and relation.

IMPORTANT: a soundness/correspondence artifact receipt is not itself a
mathematical or cultural truth proof; the external artifact verifier is a
separate trust obligation. A positive pair proof cannot prove the exclusion
of *unlisted* pairs, global categorical coherence or semantic equivalence.
No execution/admission authority is created.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol

from harness.sdk.holon_meaning_bridge import (
    ContextBindingReceiptV1,
    HolonMeaningLensV1,
    HolonMeaningReceiptV1,
    HolonMeaningVerifierV1,
)
from harness.sdk.holon_indexed_context import (
    ContextRelationReceiptV1,
    IndexedContextProblemV1,
    IndexedContextReceiptV1,
    IndexedContextVerifierV1,
)
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash, require_hash
from harness.sdk.morphisms import (
    MorphismEnvelopeV1,
    MorphismKind,
    MorphismReceiptV1,
    MorphismVerifierRegistryV1,
    SemanticProofObligationV1,
)

DOM_PAIR_PROOF_CONVENTION = "AEGIS_HOLON_CONTEXT_PAIR_PROOF_CONVENTION_V1"
DOM_PAIR_WITNESS = "AEGIS_HOLON_CONTEXT_PAIR_WITNESS_V1"
DOM_RELATION_PROOF_BUNDLE = "AEGIS_HOLON_RELATION_PROOF_BUNDLE_V1"
DOM_RELATION_PROOF_CHECK = "AEGIS_HOLON_RELATION_PROOF_CHECK_V1"
DOM_RELATION_PROOF_RECEIPT = "AEGIS_HOLON_RELATION_PROOF_RECEIPT_V1"
DOM_PROOF_BOUND_INDEXED_CHECK = "AEGIS_HOLON_PROOF_BOUND_INDEXED_CHECK_V1"
DOM_PROOF_BOUND_INDEXED_RECEIPT = "AEGIS_HOLON_PROOF_BOUND_INDEXED_RECEIPT_V1"

RELATION_PASS = "PASS_POSITIVE_MORPHISM_SUPPORT_ONLY"
JOIN_PASS = "PASS_PROOF_BOUND_FINITE_COMPATIBILITY_ONLY"
DENIED = "FAIL_CONTEXT_MORPHISM_EVIDENCE_DENIED"
MAX_PAIRS = 144
MAX_BUNDLES = 80


class ContextMorphismError(ValueError):
    pass


def _sha(name: str, value: object) -> None:
    try:
        require_hash(name, value)
    except (ValueError, TypeError) as exc:
        raise ContextMorphismError(f"{name}:INVALID_SHA256") from exc


@dataclass(frozen=True)
class ContextReadingMorphismWitnessV1:
    source_reading_id: str
    target_reading_id: str
    morphism_receipt_root: str

    def __post_init__(self) -> None:
        for name in ("source_reading_id", "target_reading_id"):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip() or len(val) > 256:
                raise ContextMorphismError(f"{name}:INVALID")
        _sha("morphism_receipt_root", self.morphism_receipt_root)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_PAIR_WITNESS, asdict(self))


@dataclass(frozen=True)
class ContextRelationProofBundleV1:
    meaning_receipt_root: str
    relation_receipt_root: str
    pair_witnesses: tuple[ContextReadingMorphismWitnessV1, ...]
    schema_version: str = field(default="aegis.holon-context-relation-proof-bundle.v1", init=False)

    def __post_init__(self) -> None:
        _sha("meaning_receipt_root", self.meaning_receipt_root)
        _sha("relation_receipt_root", self.relation_receipt_root)
        if (not isinstance(self.pair_witnesses, tuple)
                or not 1 <= len(self.pair_witnesses) <= MAX_PAIRS
                or any(not isinstance(w, ContextReadingMorphismWitnessV1) for w in self.pair_witnesses)):
            raise ContextMorphismError("PAIR_WITNESSES_INVALID")
        pairs = [(w.source_reading_id, w.target_reading_id) for w in self.pair_witnesses]
        if len(set(pairs)) != len(pairs):
            raise ContextMorphismError("PAIR_WITNESSES_DUPLICATE")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_RELATION_PROOF_BUNDLE, {
            "schema_version": self.schema_version,
            "meaning_receipt_root": self.meaning_receipt_root,
            "relation_receipt_root": self.relation_receipt_root,
            "pair_witnesses": sorted(
                (asdict(w) for w in self.pair_witnesses),
                key=lambda w: (w["source_reading_id"], w["target_reading_id"]),
            ),
        })


class TrustedRelationBundleStore(Protocol):
    def fetch_verified(self, root: str) -> ContextRelationProofBundleV1 | None: ...


class TrustedRelationStore(Protocol):
    def fetch_verified(self, root: str) -> ContextRelationReceiptV1 | None: ...


class TrustedMeaningReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> HolonMeaningReceiptV1 | None: ...


class TrustedMeaningLensStore(Protocol):
    def fetch_verified(self, root: str) -> HolonMeaningLensV1 | None: ...


class TrustedContextBindingsStore(Protocol):
    def fetch_verified(self, root: str) -> ContextBindingReceiptV1 | None: ...


class TrustedMorphismReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> MorphismReceiptV1 | None: ...


class TrustedMorphismEnvelopeStore(Protocol):
    def fetch_verified(self, root: str) -> MorphismEnvelopeV1 | None: ...


class TrustedRelationProofReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> "ContextRelationProofReceiptV1 | None": ...


@dataclass(frozen=True)
class ContextRelationProofVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class ContextRelationProofReceiptV1:
    bundle_root: str
    meaning_receipt_root: str
    relation_receipt_root: str
    verified_morphism_receipt_roots: tuple[str, ...]
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-context-relation-proof-receipt.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_RELATION_PROOF_RECEIPT, asdict(self))


def pair_proof_convention_root(
    *,
    meaning_receipt_root: str,
    lens: HolonMeaningLensV1,
    relation: ContextRelationReceiptV1,
    source_reading_id: str,
    target_reading_id: str,
    source_binding_root: str,
    target_binding_root: str,
) -> str:
    """Hash a source-specific proof *statement*, not a proof of its truth."""
    for name, root in (
        ("meaning_receipt_root", meaning_receipt_root),
        ("source_binding_root", source_binding_root),
        ("target_binding_root", target_binding_root),
    ):
        _sha(name, root)
    return canonical_hash(DOM_PAIR_PROOF_CONVENTION, {
        "meaning_receipt_root": meaning_receipt_root,
        "lens_root": lens.root,
        "holon_root": lens.holon.root,
        "occurrence_root": lens.occurrence.root,
        "relation_root": relation.root,
        "source_context_root": relation.source_context_root,
        "target_context_root": relation.target_context_root,
        "source_reading_id": source_reading_id,
        "target_reading_id": target_reading_id,
        "source_binding_root": source_binding_root,
        "target_binding_root": target_binding_root,
    })


class ContextRelationMorphismVerifierV1:
    """For every allowed pair, authenticate context-anchored SEMANTIC morphism.

    The morphism registry rechecks independently trusted proof artifacts.
    Prior-morphism chains are deliberately unsupported in this V1 strict
    verifier; they require the separate authenticated composition contract.
    """

    def __init__(
        self, *,
        bundles: TrustedRelationBundleStore,
        relations: TrustedRelationStore,
        receipts: TrustedMeaningReceiptStore,
        lenses: TrustedMeaningLensStore,
        context_bindings: TrustedContextBindingsStore,
        morphisms: TrustedMorphismReceiptStore,
        morphism_envelopes: TrustedMorphismEnvelopeStore,
        meaning_verifier: HolonMeaningVerifierV1,
        morphism_registry: MorphismVerifierRegistryV1,
    ) -> None:
        self.bundles = bundles
        self.relations = relations
        self.receipts = receipts
        self.lenses = lenses
        self.context_bindings = context_bindings
        self.morphisms = morphisms
        self.morphism_envelopes = morphism_envelopes
        self.meaning_verifier = meaning_verifier
        self.morphism_registry = morphism_registry

    def verify(
        self, bundle_root: str
    ) -> tuple[ContextRelationProofVerificationV1, ContextRelationProofReceiptV1 | None]:
        def deny(code: str):
            return ContextRelationProofVerificationV1(DENIED, (code,), None), None

        try:
            _sha("bundle_root", bundle_root)
        except ContextMorphismError:
            return deny("RELATION_BUNDLE_ROOT_INVALID")
        bundle = self.bundles.fetch_verified(bundle_root)
        if not isinstance(bundle, ContextRelationProofBundleV1) or bundle.root != bundle_root:
            return deny("RELATION_BUNDLE_UNTRUSTED")
        relation = self.relations.fetch_verified(bundle.relation_receipt_root)
        if (not isinstance(relation, ContextRelationReceiptV1)
                or relation.root != bundle.relation_receipt_root
                or relation.authority_class != NO_AUTHORITY):
            return deny("RELATION_RECEIPT_UNTRUSTED")
        receipt = self.receipts.fetch_verified(bundle.meaning_receipt_root)
        if (not isinstance(receipt, HolonMeaningReceiptV1)
                or receipt.root != bundle.meaning_receipt_root
                or receipt.authority_class != NO_AUTHORITY):
            return deny("MEANING_RECEIPT_UNTRUSTED")
        lens = self.lenses.fetch_verified(receipt.lens_root)
        if not isinstance(lens, HolonMeaningLensV1) or lens.root != receipt.lens_root:
            return deny("MEANING_LENS_UNTRUSTED")
        check, recomputed = self.meaning_verifier.verify(lens)
        if check.status != "PASS" or recomputed != receipt:
            return deny("MEANING_LINEAGE_NOT_VERIFIED")
        indexed = {r.reading_id: r for r in lens.readings}
        expected_pairs = set(relation.allowed_reading_id_pairs)
        actual_pairs = {
            (w.source_reading_id, w.target_reading_id)
            for w in bundle.pair_witnesses
        }
        if expected_pairs != actual_pairs:
            return deny("RELATION_PAIR_EVIDENCE_INCOMPLETE")
        verified = []
        for witness in sorted(
            bundle.pair_witnesses,
            key=lambda w: (w.source_reading_id, w.target_reading_id),
        ):
            source = indexed.get(witness.source_reading_id)
            target = indexed.get(witness.target_reading_id)
            if (source is None or target is None
                    or source.context_root != relation.source_context_root
                    or target.context_root != relation.target_context_root):
                return deny("RELATION_PAIR_CONTEXT_TRANSPLANT")
            source_binding = self.context_bindings.fetch_verified(source.context_binding_receipt_root)
            target_binding = self.context_bindings.fetch_verified(target.context_binding_receipt_root)
            if (not isinstance(source_binding, ContextBindingReceiptV1)
                    or source_binding.root != source.context_binding_receipt_root
                    or source_binding.authority_class != NO_AUTHORITY
                    or not isinstance(target_binding, ContextBindingReceiptV1)
                    or target_binding.root != target.context_binding_receipt_root
                    or target_binding.authority_class != NO_AUTHORITY):
                return deny("PAIR_CONTEXT_BINDING_UNTRUSTED")
            expected_convention = pair_proof_convention_root(
                meaning_receipt_root=receipt.root, lens=lens, relation=relation,
                source_reading_id=source.reading_id, target_reading_id=target.reading_id,
                source_binding_root=source_binding.root, target_binding_root=target_binding.root,
            )
            morphism = self.morphisms.fetch_verified(witness.morphism_receipt_root)
            if (not isinstance(morphism, MorphismReceiptV1)
                    or morphism.root != witness.morphism_receipt_root
                    or morphism.authority_class != NO_AUTHORITY):
                return deny("PAIR_MORPHISM_RECEIPT_UNTRUSTED")
            if (morphism.kind != MorphismKind.SEMANTIC
                    or morphism.predecessor_morphism_roots
                    or morphism.source_domain_root != source_binding.derived_root
                    or morphism.target_domain_root != target_binding.derived_root):
                return deny("PAIR_MORPHISM_ENDPOINT_OR_KIND_MISMATCH")
            envelope = self.morphism_envelopes.fetch_verified(morphism.envelope_root)
            if (not isinstance(envelope, MorphismEnvelopeV1)
                    or envelope.root != morphism.envelope_root
                    or envelope.kind != MorphismKind.SEMANTIC
                    or envelope.source_domain_root != morphism.source_domain_root
                    or envelope.target_domain_root != morphism.target_domain_root
                    or not isinstance(envelope.proof_obligation, SemanticProofObligationV1)):
                return deny("PAIR_MORPHISM_ENVELOPE_UNTRUSTED")
            if envelope.proof_obligation.convention_root != expected_convention:
                return deny("PAIR_MORPHISM_CONVENTION_TRANSPLANT")
            # Verification of the *actual* semantic morphism is delegated to
            # the existing proof-backed morphism engine, not reinvented here.
            outcome, reissued = self.morphism_registry.verify_and_issue(envelope)
            if (outcome.status != "PASS" or reissued is None
                    or reissued != morphism
                    or reissued.root != witness.morphism_receipt_root):
                return deny("PAIR_MORPHISM_PROOF_NOT_VERIFIED")
            verified.append(morphism.root)
        roots = tuple(sorted(verified))
        verification_root = canonical_hash(DOM_RELATION_PROOF_CHECK, {
            "bundle_root": bundle_root,
            "meaning_receipt_root": receipt.root,
            "relation_receipt_root": relation.root,
            "verified_morphism_receipt_roots": roots,
            "status": RELATION_PASS,
        })
        evidence = ContextRelationProofReceiptV1(
            bundle_root, receipt.root, relation.root, roots, verification_root,
        )
        return ContextRelationProofVerificationV1(RELATION_PASS, (), verification_root), evidence


@dataclass(frozen=True)
class ProofBoundIndexedContextReceiptV1:
    indexed_receipt_root: str
    relation_proof_receipt_roots: tuple[str, ...]
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-proof-bound-indexed-context.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_PROOF_BOUND_INDEXED_RECEIPT, asdict(self))


class ProofBoundIndexedContextVerifierV1:
    """Join independently valid finite solver evidence with all pair proofs."""

    def __init__(
        self, *,
        indexed: IndexedContextVerifierV1,
        relation_verifier: ContextRelationMorphismVerifierV1,
        relation_proof_receipts: TrustedRelationProofReceiptStore,
    ) -> None:
        self.indexed = indexed
        self.relation_verifier = relation_verifier
        self.relation_proof_receipts = relation_proof_receipts

    def verify(
        self,
        problem_root: str,
        relation_proof_receipt_roots: tuple[str, ...],
    ) -> tuple[ContextRelationProofVerificationV1, ProofBoundIndexedContextReceiptV1 | None]:
        def deny(code: str):
            return ContextRelationProofVerificationV1(DENIED, (code,), None), None

        if (not isinstance(relation_proof_receipt_roots, tuple)
                or len(relation_proof_receipt_roots) > MAX_BUNDLES
                or len(set(relation_proof_receipt_roots)) != len(relation_proof_receipt_roots)):
            return deny("INDEXED_RELATION_PROOF_SET_INVALID")
        for root in relation_proof_receipt_roots:
            try:
                _sha("relation_proof_receipt_root", root)
            except ContextMorphismError:
                return deny("INDEXED_RELATION_PROOF_ROOT_INVALID")
        problem = self.indexed.problems.fetch_verified(problem_root)
        if not isinstance(problem, IndexedContextProblemV1) or problem.root != problem_root:
            return deny("INDEXED_PROBLEM_UNTRUSTED")
        result, indexed_receipt = self.indexed.verify(problem_root)
        # Positive proof support does NOT imply any unlisted pair is impossible,
        # so this strict join intentionally refuses to certify UNSAT as truth.
        if result.status != "PASS_FINITE_COMPATIBILITY_ONLY" or not isinstance(indexed_receipt, IndexedContextReceiptV1):
            return deny("INDEXED_BASE_NOT_FINITE_PASS")
        proof_roots = []
        covered_relation_roots = []
        for root in sorted(relation_proof_receipt_roots):
            prior = self.relation_proof_receipts.fetch_verified(root)
            if (not isinstance(prior, ContextRelationProofReceiptV1)
                    or prior.root != root or prior.authority_class != NO_AUTHORITY):
                return deny("INDEXED_RELATION_PROOF_UNTRUSTED")
            result, newly_verified = self.relation_verifier.verify(prior.bundle_root)
            if result.status != RELATION_PASS or newly_verified != prior:
                return deny("INDEXED_RELATION_PROOF_NOT_REPLAYED")
            if prior.meaning_receipt_root != indexed_receipt.meaning_receipt_root:
                return deny("INDEXED_RELATION_MEANING_SCOPE_MISMATCH")
            covered_relation_roots.append(prior.relation_receipt_root)
            proof_roots.append(root)
        if (tuple(sorted(covered_relation_roots))
                != tuple(sorted(problem.relation_receipt_roots))):
            return deny("INDEXED_RELATION_PROOFS_INCOMPLETE")
        ordered = tuple(sorted(proof_roots))
        verification_root = canonical_hash(DOM_PROOF_BOUND_INDEXED_CHECK, {
            "indexed_receipt_root": indexed_receipt.root,
            "relation_proof_receipt_roots": ordered,
            "status": JOIN_PASS,
        })
        evidence = ProofBoundIndexedContextReceiptV1(
            indexed_receipt.root, ordered, verification_root,
        )
        return ContextRelationProofVerificationV1(JOIN_PASS, (), verification_root), evidence
