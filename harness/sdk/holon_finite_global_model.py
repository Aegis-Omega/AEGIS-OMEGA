"""Finite shared-valuation coherence over authenticated AEGIS MHP readings.

Pairwise satisfiability of formal readings does not imply a common Boolean
valuation across every context (e.g. p, q, not(p and q)). This verifier replays
each existing finite-formal relation verifier, then checks ALL contexts against
one shared, exact, sorted Boolean variable universe.

The result is a proof only in the finite formal model of exact derived formula
bytes. Neither the faithful interpretation of speech nor a categorical global
section nor execution authority follows from this computation.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Protocol

from harness.sdk.holon_finite_semantics import (
    FiniteBooleanError,
    FiniteFormalRelationReceiptV1,
    FiniteFormalRelationVerifierV1,
    PASS as FORMAL_RELATION_PASS,
    finite_truth_mask,
    parse_formal_reading,
)
from harness.sdk.holon_indexed_context import (
    DENIED as INDEX_DENIED,
    IndexedContextProblemV1,
    IndexedContextVerifierV1,
)
from harness.sdk.holon_meaning_bridge import ContextBindingReceiptV1, HolonMeaningLensV1, HolonMeaningReceiptV1
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash, require_hash

DOMAIN_CHECK = "AEGIS_HOLON_FINITE_GLOBAL_VALUATION_CHECK_V1"
DOMAIN_RECEIPT = "AEGIS_HOLON_FINITE_GLOBAL_VALUATION_RECEIPT_V1"

SAT = "PROVEN_SHARED_FINITE_BOOLEAN_MODEL"
UNSAT = "PROVEN_NO_SHARED_FINITE_BOOLEAN_MODEL"
DENIED = "FAIL_FINITE_GLOBAL_EVIDENCE_DENIED"

MAX_CONTEXTS = 12
MAX_READINGS = 144
MAX_RELATIONS = 80


class FiniteGlobalError(ValueError):
    pass


def _sha(name: str, root: object) -> None:
    try:
        require_hash(name, root)
    except (TypeError, ValueError) as exc:
        raise FiniteGlobalError(f"{name}:INVALID_SHA256") from exc


@dataclass(frozen=True)
class FiniteGlobalVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class FiniteGlobalModelReceiptV1:
    problem_root: str
    meaning_receipt_root: str
    verified_relation_receipt_roots: tuple[str, ...]
    verified_formal_relation_proof_roots: tuple[str, ...]
    verified_formal_artifact_roots: tuple[str, ...]
    variables: tuple[str, ...]
    valuation_count: int
    context_truth_union_masks_hex: tuple[tuple[str, str], ...]
    global_truth_mask_hex: str
    shared_valuation_count: int
    model_kind: str
    valuation_index: int | None
    selected_readings: tuple[tuple[str, str], ...]
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-finite-global-model.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOMAIN_RECEIPT, asdict(self))


class FiniteGlobalModelVerifierV1:
    """Replay exact MHP lineage, every complete pair-table proof, global model.

    The source MHP artifact store, indexed graph store and finite relation
    verifier are separately trusted inputs. Content hash alone is not proof of
    source intent, external evidence authenticity or scientific soundness.
    """

    def __init__(
        self, *,
        indexed: IndexedContextVerifierV1,
        formal: FiniteFormalRelationVerifierV1,
    ) -> None:
        self.indexed = indexed
        self.formal = formal

    def verify(
        self, problem_root: str
    ) -> tuple[FiniteGlobalVerificationV1, FiniteGlobalModelReceiptV1 | None]:
        def deny(code: str):
            return FiniteGlobalVerificationV1(DENIED, (code,), None), None

        try:
            _sha("problem_root", problem_root)
        except FiniteGlobalError:
            return deny("GLOBAL_PROBLEM_ROOT_INVALID")

        problem = self.indexed.problems.fetch_verified(problem_root)
        if not isinstance(problem, IndexedContextProblemV1) or problem.root != problem_root:
            return deny("GLOBAL_INDEX_PROBLEM_UNTRUSTED")

        # Replay MHP, topology and declared relation graph through existing
        # verifier. OPEN is computational, not an epistemic denial; we can
        # resolve the shared finite Boolean model independently in <= 256 bits.
        index_result, _ = self.indexed.verify(problem_root)
        if index_result.status == INDEX_DENIED:
            return deny("GLOBAL_INDEX_VERIFICATION_DENIED")
        if index_result.status not in (
            "PASS_FINITE_COMPATIBILITY_ONLY",
            "NO_FINITE_ASSIGNMENT_RELATIVE_TO_ATTESTED_RELATIONS",
            "OPEN_FINITE_SEARCH_BUDGET",
        ):
            return deny("GLOBAL_INDEX_UNEXPECTED_RESULT")

        receipt = self.formal.meanings.fetch_verified(problem.meaning_receipt_root)
        if (not isinstance(receipt, HolonMeaningReceiptV1)
                or receipt.root != problem.meaning_receipt_root
                or receipt.authority_class != NO_AUTHORITY):
            return deny("GLOBAL_MHP_RECEIPT_UNTRUSTED")
        lens = self.formal.lenses.fetch_verified(receipt.lens_root)
        if not isinstance(lens, HolonMeaningLensV1) or lens.root != receipt.lens_root:
            return deny("GLOBAL_MHP_LENS_UNTRUSTED")
        check, replay = self.formal.meaning_verifier.verify(lens)
        if check.status != "PASS" or replay != receipt:
            return deny("GLOBAL_MHP_REPLAY_FAILED")
        if (not 2 <= len({r.context_root for r in lens.readings}) <= MAX_CONTEXTS
                or not lens.readings or len(lens.readings) > MAX_READINGS
                or not 1 <= len(problem.relation_receipt_roots) <= MAX_RELATIONS):
            return deny("GLOBAL_SCOPE_NOT_MULTICONTEXT")

        # Every indexed edge gets independently replayed complete Boolean-pair
        # evidence. In particular, the negative edges are justified by fully
        # checking the finite truth tables, not by a missing positive proof.
        relations = {}
        proven = []
        for relation_root in sorted(problem.relation_receipt_roots):
            outcome, proof = self.formal.verify(receipt.root, relation_root)
            if outcome.status != FORMAL_RELATION_PASS or not isinstance(proof, FiniteFormalRelationReceiptV1):
                return deny("GLOBAL_FORMAL_PAIR_TABLE_UNVERIFIED")
            relation = self.formal.relations.fetch_verified(relation_root)
            if relation is None or relation.root != relation_root:
                return deny("GLOBAL_RELATION_UNTRUSTED")
            relations[relation_root] = relation
            proven.append(proof.root)

        # All formulas are independently re-read through the already verified
        # context bindings, then checked under ONE global variable universe.
        # Pair proofs on the same number of variables but DIFFERENT names must
        # never be merged merely because their truth masks have equal length.
        groups: dict[str, list[str]] = defaultdict(list)
        truth: dict[str, int] = {}
        artifact_roots = []
        variable_names: tuple[str, ...] | None = None
        for reading in lens.readings:
            binding = self.formal.bindings.fetch_verified(reading.context_binding_receipt_root)
            if (not isinstance(binding, ContextBindingReceiptV1)
                    or binding.root != reading.context_binding_receipt_root
                    or binding.authority_class != NO_AUTHORITY
                    or binding.reading_id != reading.reading_id
                    or binding.holon_root != lens.holon.root
                    or binding.occurrence_root != lens.occurrence.root
                    or binding.context_root != reading.context_root
                    or binding.envelope_root != reading.envelope_root):
                return deny("GLOBAL_CONTEXT_BINDING_UNTRUSTED")
            raw = self.formal.artifacts.fetch_verified(binding.derived_root)
            if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != binding.derived_root:
                return deny("GLOBAL_FORMAL_BYTES_UNTRUSTED")
            try:
                formula = parse_formal_reading(raw)
            except FiniteBooleanError:
                return deny("GLOBAL_FORMAL_FORMULA_INVALID")
            if variable_names is None:
                variable_names = formula.variables
            elif variable_names != formula.variables:
                return deny("GLOBAL_VARIABLE_UNIVERSE_MISMATCH")
            if reading.reading_id in truth:
                return deny("GLOBAL_DUPLICATE_READING_ID")
            truth[reading.reading_id] = finite_truth_mask(formula)
            groups[reading.context_root].append(reading.reading_id)
            artifact_roots.append(formula.artifact_root)

        if variable_names is None or set(groups) != {r.context_root for r in lens.readings}:
            return deny("GLOBAL_CONTEXT_COVERAGE_INVALID")
        ordered_contexts = tuple(sorted(groups))
        for context_root in ordered_contexts:
            groups[context_root].sort()
        # Every relation must actually connect two indexed contextual fibers.
        if any(r.source_context_root not in groups or r.target_context_root not in groups
               for r in relations.values()):
            return deny("GLOBAL_RELATION_SCOPE_INVALID")

        count = 1 << len(variable_names)
        # A context may contain several alternative formal readings.
        # Union their truth masks; intersect the context masks globally.
        # Bits encode ALL (<= 2^8) Boolean valuations in a shared universe.
        context_unions = []
        global_truth_mask = (1 << count) - 1
        for ctx in ordered_contexts:
            local_mask = 0
            for name in groups[ctx]:
                local_mask |= truth[name]
            context_unions.append((ctx, f"{local_mask:064x}"))
            global_truth_mask &= local_mask
        shared_valuation_count = global_truth_mask.bit_count()
        witness = (
            (global_truth_mask & -global_truth_mask).bit_length() - 1
            if global_truth_mask else None
        )
        selected = ()
        if witness is not None:
            selected = tuple(
                (ctx, next(name for name in groups[ctx] if truth[name] & (1 << witness)))
                for ctx in ordered_contexts
            )
            assignment = dict(selected)
            if any(
                (assignment[r.source_context_root], assignment[r.target_context_root])
                not in r.allowed_reading_id_pairs
                for r in relations.values()
            ):
                # Each pair table was independently proved complete for the
                # exact same formulas. Such a mismatch is a verifier failure,
                # not permission to silently choose a different interpretation.
                return deny("GLOBAL_FORMAL_PAIR_INVARIANT_BROKEN")

        result_kind = SAT if witness is not None else UNSAT
        relations_roots = tuple(sorted(relations))
        formal_roots = tuple(sorted(proven))
        artifacts_roots = tuple(sorted(set(artifact_roots)))
        verification_root = canonical_hash(DOMAIN_CHECK, {
            "problem_root": problem_root,
            "meaning_receipt_root": receipt.root,
            "verified_relation_receipt_roots": relations_roots,
            "verified_formal_relation_proof_roots": formal_roots,
            "verified_formal_artifact_roots": artifacts_roots,
            "variables": variable_names,
            "valuation_count": count,
            "context_truth_union_masks_hex": tuple(context_unions),
            "global_truth_mask_hex": f"{global_truth_mask:064x}",
            "shared_valuation_count": shared_valuation_count,
            "model_kind": result_kind,
            "valuation_index": witness,
            "selected_readings": selected,
        })
        proof = FiniteGlobalModelReceiptV1(
            problem_root, receipt.root, relations_roots, formal_roots,
            artifacts_roots, variable_names, count, tuple(context_unions),
            f"{global_truth_mask:064x}", shared_valuation_count,
            result_kind, witness, selected, verification_root,
        )
        return FiniteGlobalVerificationV1(result_kind, (), verification_root), proof



class TrustedFiniteGlobalReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> FiniteGlobalModelReceiptV1 | None: ...


class FiniteGlobalReceiptReplayVerifierV1:
    """Re-check an already issued SAT/UNSAT claim against current trusted evidence.

    This checks custody and repeatability, not independent mathematical
    correctness: the same finite verifier is rerun. Replaying an old receipt
    cannot silently admit changed source bytes, contexts or proof tables.
    """

    def __init__(
        self,
        *,
        receipts: TrustedFiniteGlobalReceiptStore,
        verifier: FiniteGlobalModelVerifierV1,
    ) -> None:
        self.receipts = receipts
        self.verifier = verifier

    def verify(
        self, receipt_root: str
    ) -> tuple[FiniteGlobalVerificationV1, FiniteGlobalModelReceiptV1 | None]:
        def deny(code: str):
            return FiniteGlobalVerificationV1(DENIED, (code,), None), None

        try:
            _sha("global_receipt_root", receipt_root)
        except FiniteGlobalError:
            return deny("GLOBAL_REPLAY_ROOT_INVALID")
        stored = self.receipts.fetch_verified(receipt_root)
        if (not isinstance(stored, FiniteGlobalModelReceiptV1)
                or stored.root != receipt_root
                or stored.authority_class != NO_AUTHORITY):
            return deny("GLOBAL_REPLAY_RECEIPT_UNTRUSTED")
        check, recomputed = self.verifier.verify(stored.problem_root)
        if (check.status not in (SAT, UNSAT)
                or not isinstance(recomputed, FiniteGlobalModelReceiptV1)):
            return deny("GLOBAL_REPLAY_EVIDENCE_NO_LONGER_VALID")
        if (recomputed != stored
                or recomputed.root != receipt_root
                or recomputed.verification_root != check.verification_root):
            return deny("GLOBAL_REPLAY_CONTENT_CHANGED")
        return check, recomputed
