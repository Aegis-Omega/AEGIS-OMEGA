"""Bounded, evidence-bound finite indexed-context compatibility for AEGIS MHP-1.

This is a finite constraint analogue of selecting compatible representatives
from context-indexed fibers. It is NOT a categorical fibration proof, a global
Cartesian-section theorem, a claim of semantic equivalence or temporal change,
or any form of action authority.

The source MHP lens and receipts are checked by the existing verifier.
Relation receipts are separately trusted input; their provenance/soundness
remain obligations of the external trusted evidence store.
"""
from __future__ import annotations

import itertools
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from typing import Protocol

from harness.sdk.holon_meaning_bridge import (
    HolonMeaningLensV1,
    HolonMeaningReceiptV1,
    HolonMeaningVerifierV1,
)
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash, require_hash

DOM_RELATION = "AEGIS_HOLON_CONTEXT_RELATION_V1"
DOM_PROBLEM = "AEGIS_HOLON_INDEXED_CONTEXT_PROBLEM_V1"
DOM_CHECK = "AEGIS_HOLON_INDEXED_CONTEXT_CHECK_V1"
DOM_RECEIPT = "AEGIS_HOLON_INDEXED_CONTEXT_RECEIPT_V1"
PASS = "PASS_FINITE_COMPATIBILITY_ONLY"
NO_SOLUTION = "NO_FINITE_ASSIGNMENT_RELATIVE_TO_ATTESTED_RELATIONS"
DENIED = "FAIL_INDEXED_CONTEXT_EVIDENCE_DENIED"
OPEN = "OPEN_FINITE_SEARCH_BUDGET"
MAX_CONTEXTS = 12
MAX_READINGS_PER_CONTEXT = 12
MAX_RELATIONS = 80
MAX_COMBINATIONS = 32768
MAX_ALLOWED_PAIRS = 144


class IndexedContextError(ValueError):
    pass


def _sha(key: str, value: object) -> None:
    try:
        require_hash(key, value)
    except (TypeError, ValueError) as exc:
        raise IndexedContextError(f"{key}:INVALID") from exc


@dataclass(frozen=True)
class ContextRelationReceiptV1:
    """Read-only claim that explicitly listed candidate pairs are compatible.

    Externally trusted store review of actual relation/proof soundness is a
    separate precondition; this record alone is not a proof of that soundness.
    """

    source_context_root: str
    target_context_root: str
    allowed_reading_id_pairs: tuple[tuple[str, str], ...]
    verifier_root: str
    policy_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-context-relation.v1", init=False)

    def __post_init__(self) -> None:
        for key in ("source_context_root", "target_context_root", "verifier_root", "policy_root"):
            _sha(key, getattr(self, key))
        if self.source_context_root == self.target_context_root:
            raise IndexedContextError("RELATION_SELF_CONTEXT")
        if not isinstance(self.allowed_reading_id_pairs, tuple) or len(self.allowed_reading_id_pairs) > MAX_ALLOWED_PAIRS:
            raise IndexedContextError("RELATION_PAIRS_INVALID")
        for pair in self.allowed_reading_id_pairs:
            if (not isinstance(pair, tuple) or len(pair) != 2
                    or any(not isinstance(x, str) or not x.strip() for x in pair)):
                raise IndexedContextError("RELATION_PAIR_INVALID")
        if len(set(self.allowed_reading_id_pairs)) != len(self.allowed_reading_id_pairs):
            raise IndexedContextError("RELATION_PAIR_DUPLICATE")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_RELATION, asdict(self))


@dataclass(frozen=True)
class IndexedContextProblemV1:
    meaning_receipt_root: str
    relation_receipt_roots: tuple[str, ...]
    schema_version: str = field(default="aegis.holon-indexed-context-problem.v1", init=False)

    def __post_init__(self) -> None:
        _sha("meaning_receipt_root", self.meaning_receipt_root)
        if not isinstance(self.relation_receipt_roots, tuple) or len(self.relation_receipt_roots) > MAX_RELATIONS:
            raise IndexedContextError("PROBLEM_RELATIONS_INVALID")
        for root in self.relation_receipt_roots:
            _sha("relation_receipt_root", root)
        if len(set(self.relation_receipt_roots)) != len(self.relation_receipt_roots):
            raise IndexedContextError("PROBLEM_RELATION_DUPLICATE")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_PROBLEM, {
            "schema_version": self.schema_version,
            "meaning_receipt_root": self.meaning_receipt_root,
            "relation_receipt_roots": sorted(self.relation_receipt_roots),
        })


class TrustedIndexedContextProblemStore(Protocol):
    def fetch_verified(self, root: str) -> IndexedContextProblemV1 | None: ...


class TrustedContextRelationReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> ContextRelationReceiptV1 | None: ...


class TrustedMeaningReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> HolonMeaningReceiptV1 | None: ...


class TrustedMeaningLensStore(Protocol):
    def fetch_verified(self, root: str) -> HolonMeaningLensV1 | None: ...


@dataclass(frozen=True)
class IndexedContextVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class IndexedContextReceiptV1:
    problem_root: str
    meaning_receipt_root: str
    relation_receipt_roots: tuple[str, ...]
    selected_readings: tuple[tuple[str, str], ...]
    search_space_bound: int
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-indexed-context-receipt.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_RECEIPT, asdict(self))


def solve_finite_fiber_constraints(
    fibers: tuple[tuple[str, tuple[str, ...]], ...],
    constraints: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...],
) -> tuple[str, tuple[tuple[str, str], ...] | None, int]:
    """Pure finite enumeration. NO cryptographic trust claims are made here.

    A returned NO_SOLUTION is only relative to the supplied finite relations.
    This does not establish inexistence of a global Cartesian section of a
    categorical fibration, whose coherence/morphisms are not encoded here.
    """
    if not isinstance(fibers, tuple) or not 1 <= len(fibers) <= MAX_CONTEXTS:
        raise IndexedContextError("FIBERS_INVALID")
    if len({f[0] for f in fibers}) != len(fibers):
        raise IndexedContextError("FIBER_DUPLICATE_CONTEXT")
    items: dict[str, tuple[str, ...]] = {}
    bound = 1
    for ctx, choices in fibers:
        _sha("context_root", ctx)
        if (not isinstance(choices, tuple) or not 1 <= len(choices) <= MAX_READINGS_PER_CONTEXT
                or any(not isinstance(v, str) or not v.strip() for v in choices)
                or len(set(choices)) != len(choices)):
            raise IndexedContextError("FIBER_CHOICES_INVALID")
        items[ctx] = tuple(sorted(choices))
        bound *= len(choices)
    if bound > MAX_COMBINATIONS:
        return OPEN, None, bound

    if not isinstance(constraints, tuple) or len(constraints) > MAX_RELATIONS:
        raise IndexedContextError("CONSTRAINTS_INVALID")
    edges: dict[tuple[str, str], set[tuple[str, str]]] = {}
    undirected = defaultdict(set)
    for source, target, pairs in constraints:
        if source not in items or target not in items or source == target:
            raise IndexedContextError("CONSTRAINT_CONTEXT_INVALID")
        edge = source, target
        if edge in edges:
            raise IndexedContextError("CONSTRAINT_EDGE_DUPLICATE")
        if not isinstance(pairs, tuple) or len(pairs) > MAX_ALLOWED_PAIRS:
            raise IndexedContextError("CONSTRAINT_PAIRS_INVALID")
        if any(pair[0] not in items[source] or pair[1] not in items[target] for pair in pairs):
            raise IndexedContextError("CONSTRAINT_PAIR_NOT_IN_FIBERS")
        edges[edge] = set(pairs)
        undirected[source].add(target)
        undirected[target].add(source)

    # In a multi-context problem, an unconnected index cannot silently
    # masquerade as having cross-context compatibility evidence.
    if len(items) > 1:
        start = min(items)
        seen = {start}
        queue = deque([start])
        while queue:
            source = queue.popleft()
            for target in sorted(undirected[source]):
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
        if seen != set(items):
            raise IndexedContextError("CONTEXT_INDEX_UNCONNECTED")

    ordered = sorted(items)
    for values in itertools.product(*(items[ctx] for ctx in ordered)):
        assignment = dict(zip(ordered, values))
        if all((assignment[a], assignment[b]) in allowed for (a, b), allowed in edges.items()):
            return PASS, tuple(zip(ordered, values)), bound
    return NO_SOLUTION, None, bound


class IndexedContextVerifierV1:
    def __init__(
        self, *, problems: TrustedIndexedContextProblemStore,
        relations: TrustedContextRelationReceiptStore,
        receipts: TrustedMeaningReceiptStore,
        lenses: TrustedMeaningLensStore,
        meaning_verifier: HolonMeaningVerifierV1,
    ) -> None:
        self.problems = problems
        self.relations = relations
        self.receipts = receipts
        self.lenses = lenses
        self.meaning_verifier = meaning_verifier

    def verify(
        self, problem_root: str
    ) -> tuple[IndexedContextVerificationV1, IndexedContextReceiptV1 | None]:
        def deny(code: str):
            return IndexedContextVerificationV1(DENIED, (code,), None), None

        try:
            _sha("problem_root", problem_root)
        except IndexedContextError:
            return deny("PROBLEM_ROOT_INVALID")
        problem = self.problems.fetch_verified(problem_root)
        if not isinstance(problem, IndexedContextProblemV1) or problem.root != problem_root:
            return deny("PROBLEM_UNTRUSTED")
        receipt = self.receipts.fetch_verified(problem.meaning_receipt_root)
        if (not isinstance(receipt, HolonMeaningReceiptV1)
                or receipt.root != problem.meaning_receipt_root or receipt.authority_class != NO_AUTHORITY):
            return deny("MEANING_RECEIPT_UNTRUSTED")
        lens = self.lenses.fetch_verified(receipt.lens_root)
        if not isinstance(lens, HolonMeaningLensV1) or lens.root != receipt.lens_root:
            return deny("MEANING_LENS_UNTRUSTED")
        result, recomputed = self.meaning_verifier.verify(lens)
        if result.status != "PASS" or recomputed != receipt:
            return deny("MEANING_LINEAGE_VERIFICATION_FAILED")
        groups: dict[str, list[str]] = defaultdict(list)
        for reading in lens.readings:
            groups[reading.context_root].append(reading.reading_id)
        fibers = tuple((key, tuple(values)) for key, values in sorted(groups.items()))
        relation_records: list[ContextRelationReceiptV1] = []
        for relation_root in sorted(problem.relation_receipt_roots):
            rel = self.relations.fetch_verified(relation_root)
            if (not isinstance(rel, ContextRelationReceiptV1)
                    or rel.root != relation_root or rel.authority_class != NO_AUTHORITY):
                return deny("RELATION_RECEIPT_UNTRUSTED")
            relation_records.append(rel)
        constraints = tuple(
            (r.source_context_root, r.target_context_root, r.allowed_reading_id_pairs)
            for r in relation_records
        )
        try:
            status, selected, bound = solve_finite_fiber_constraints(fibers, constraints)
        except IndexedContextError as exc:
            return deny(str(exc))
        if status == OPEN:
            return IndexedContextVerificationV1(OPEN, ("SEARCH_SPACE_BOUND_EXCEEDED",), None), None
        if status == NO_SOLUTION:
            return IndexedContextVerificationV1(NO_SOLUTION, ("NO_ASSIGNMENT_FOR_ATTESTED_RELATIONS",), None), None
        assert selected is not None
        verification_root = canonical_hash(DOM_CHECK, {
            "problem_root": problem_root,
            "meaning_receipt_root": receipt.root,
            "relation_receipt_roots": sorted(problem.relation_receipt_roots),
            "selected_readings": selected,
            "search_space_bound": bound,
            "status": PASS,
        })
        evidence = IndexedContextReceiptV1(
            problem_root, receipt.root, tuple(sorted(problem.relation_receipt_roots)),
            selected, bound, verification_root,
        )
        return IndexedContextVerificationV1(PASS, (), verification_root), evidence
