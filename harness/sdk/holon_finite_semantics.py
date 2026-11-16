"""Executable, complete finite Boolean interpretation relation proof for AEGIS.

Finite-formal lane only. Reads actual derived MHP artifact bytes as *canonical*
Boolean formula JSON; computes every truth value in a shared bounded valuation
space. It never interprets arbitrary natural-language strings, extrapolates a
Boolean model from speech, proves author intent, or grants action authority.

This is a decidable, locally executable semantic kernel. The *assumption* that
a formally encoded proposition faithfully represents a natural utterance is
NOT discharged here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from harness.sdk.holon_meaning_bridge import (
    ContextBindingReceiptV1,
    HolonMeaningLensV1,
    HolonMeaningReceiptV1,
    HolonMeaningVerifierV1,
)
from harness.sdk.holon_indexed_context import ContextRelationReceiptV1
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash, require_hash
from harness.sdk.sovereign_execution import canonical_bytes

DOM_FINITE_TRUTH_CHECK = "AEGIS_HOLON_FINITE_BOOLEAN_TRUTH_CHECK_V1"
DOM_FINITE_TRUTH_RECEIPT = "AEGIS_HOLON_FINITE_BOOLEAN_TRUTH_RECEIPT_V1"
SCHEMA = "aegis.finite-boolean-reading.v1"
PASS = "PASS_EXHAUSTIVE_FORMAL_RELATION_ONLY"
DENIED = "FAIL_FINITE_FORMAL_RELATION_DENIED"
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z")
MAX_VARIABLES = 8
MAX_AST_DEPTH = 12
MAX_AST_NODES = 128
MAX_FORMULA_BYTES = 8192
MAX_READINGS_PER_CONTEXT = 12


class FiniteBooleanError(ValueError):
    pass


def _sha(name: str, root: object) -> str:
    try:
        require_hash(name, root)
    except (ValueError, TypeError) as exc:
        raise FiniteBooleanError(f"{name}:INVALID_SHA256") from exc
    return root


def _distinct_pairs(entries: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in entries:
        if k in result:
            raise FiniteBooleanError("FORMULA_DUPLICATE_JSON_KEY")
        result[k] = v
    return result


def _parse_tree(node: object, vars_: set[str], depth: int, budget: list[int]) -> None:
    budget[0] += 1
    if budget[0] > MAX_AST_NODES or depth > MAX_AST_DEPTH:
        raise FiniteBooleanError("FORMULA_AST_LIMIT_EXCEEDED")
    if type(node) is not dict:
        raise FiniteBooleanError("FORMULA_AST_SHAPE_INVALID")
    op = node.get("op")
    if op == "var":
        if (set(node) != {"op", "name"}
                or type(node["name"]) is not str
                or node["name"] not in vars_):
            raise FiniteBooleanError("FORMULA_VARIABLE_NOT_DECLARED")
    elif op == "const":
        if set(node) != {"op", "value"} or type(node["value"]) is not bool:
            raise FiniteBooleanError("FORMULA_CONSTANT_INVALID")
    elif op == "not":
        if set(node) != {"op", "arg"}:
            raise FiniteBooleanError("FORMULA_NOT_SHAPE_INVALID")
        _parse_tree(node["arg"], vars_, depth + 1, budget)
    elif op in ("and", "or"):
        args = node.get("args")
        if set(node) != {"op", "args"} or type(args) is not list or not 2 <= len(args) <= 4:
            raise FiniteBooleanError("FORMULA_CONNECTIVE_SHAPE_INVALID")
        for arg in args:
            _parse_tree(arg, vars_, depth + 1, budget)
    else:
        raise FiniteBooleanError("FORMULA_OPERATOR_UNSUPPORTED")


@dataclass(frozen=True)
class FiniteBooleanFormulaV1:
    variables: tuple[str, ...]
    formula: dict[str, Any]
    artifact_root: str

    def __post_init__(self) -> None:
        _sha("artifact_root", self.artifact_root)


def parse_formal_reading(payload: bytes) -> FiniteBooleanFormulaV1:
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_FORMULA_BYTES:
        raise FiniteBooleanError("FORMULA_BYTES_INVALID")
    try:
        doc = json.loads(payload.decode("utf-8"), object_pairs_hook=_distinct_pairs)
    except FiniteBooleanError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FiniteBooleanError("FORMULA_JSON_INVALID") from exc
    if type(doc) is not dict or set(doc) != {"schema", "variables", "formula"} or doc["schema"] != SCHEMA:
        raise FiniteBooleanError("FORMULA_SCHEMA_INVALID")
    vars_ = doc["variables"]
    if (type(vars_) is not list or len(vars_) > MAX_VARIABLES
            or any(type(x) is not str or IDENTIFIER.fullmatch(x) is None for x in vars_)
            or vars_ != sorted(set(vars_))):
        raise FiniteBooleanError("FORMULA_VARIABLES_INVALID")
    _parse_tree(doc["formula"], set(vars_), 0, [0])
    if canonical_bytes(doc) != payload:
        raise FiniteBooleanError("FORMULA_BYTES_NONCANONICAL")
    return FiniteBooleanFormulaV1(tuple(vars_), doc["formula"], hashlib.sha256(payload).hexdigest())


def _value(node: dict[str, Any], assignment: dict[str, bool]) -> bool:
    op = node["op"]
    if op == "var":
        return assignment[node["name"]]
    if op == "const":
        return node["value"]
    if op == "not":
        return not _value(node["arg"], assignment)
    if op == "and":
        return all(_value(arg, assignment) for arg in node["args"])
    if op == "or":
        return any(_value(arg, assignment) for arg in node["args"])
    raise AssertionError("validated formula invariant lost")


def finite_truth_mask(formula: FiniteBooleanFormulaV1) -> int:
    """Bit i is truth at valuation i in sorted variable order.

    Exhaustive evaluation over at most 2^8 valuations is the proof kernel.
    """
    total = 1 << len(formula.variables)
    mask = 0
    for i in range(total):
        valuation = {key: bool(i & (1 << j)) for j, key in enumerate(formula.variables)}
        if _value(formula.formula, valuation):
            mask |= 1 << i
    return mask


class TrustedFiniteArtifactStore(Protocol):
    def fetch_verified(self, root: str) -> bytes | None: ...


class TrustedFiniteRelationStore(Protocol):
    def fetch_verified(self, root: str) -> ContextRelationReceiptV1 | None: ...


class TrustedFiniteMeaningStore(Protocol):
    def fetch_verified(self, root: str) -> HolonMeaningReceiptV1 | None: ...


class TrustedFiniteLensStore(Protocol):
    def fetch_verified(self, root: str) -> HolonMeaningLensV1 | None: ...


class TrustedFiniteBindingStore(Protocol):
    def fetch_verified(self, root: str) -> ContextBindingReceiptV1 | None: ...


@dataclass(frozen=True)
class FiniteFormalRelationVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class FiniteFormalRelationReceiptV1:
    meaning_receipt_root: str
    relation_receipt_root: str
    verified_formal_artifact_roots: tuple[str, ...]
    reading_truth_masks_hex: tuple[tuple[str, str], ...]
    valuation_count: int
    checked_pair_count: int
    compatible_pair_count: int
    incompatible_pair_count: int
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-finite-formal-relation.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_FINITE_TRUTH_RECEIPT, asdict(self))


class FiniteFormalRelationVerifierV1:
    """Proves the COMPLETE binary compatibility table in formal Boolean syntax.

    Completeness is relative to exact source and target MHP context fibers.
    A pair is compatible iff the two formal statements have a joint satisfying
    Boolean valuation. This does NOT establish the faithfulness of the formal
    statements to natural language, or the truth of the two statements.
    """

    def __init__(
        self, *,
        relations: TrustedFiniteRelationStore,
        meanings: TrustedFiniteMeaningStore,
        lenses: TrustedFiniteLensStore,
        bindings: TrustedFiniteBindingStore,
        artifacts: TrustedFiniteArtifactStore,
        meaning_verifier: HolonMeaningVerifierV1,
    ) -> None:
        self.relations = relations
        self.meanings = meanings
        self.lenses = lenses
        self.bindings = bindings
        self.artifacts = artifacts
        self.meaning_verifier = meaning_verifier

    def verify(
        self, meaning_receipt_root: str, relation_root: str
    ) -> tuple[FiniteFormalRelationVerificationV1, FiniteFormalRelationReceiptV1 | None]:
        def deny(code: str):
            return FiniteFormalRelationVerificationV1(DENIED, (code,), None), None

        try:
            _sha("meaning_receipt_root", meaning_receipt_root)
            _sha("relation_root", relation_root)
        except FiniteBooleanError:
            return deny("FINITE_FORMAL_INPUT_ROOT_INVALID")
        receipt = self.meanings.fetch_verified(meaning_receipt_root)
        if (not isinstance(receipt, HolonMeaningReceiptV1)
                or receipt.root != meaning_receipt_root or receipt.authority_class != NO_AUTHORITY):
            return deny("FINITE_FORMAL_MHP_RECEIPT_UNTRUSTED")
        lens = self.lenses.fetch_verified(receipt.lens_root)
        if not isinstance(lens, HolonMeaningLensV1) or lens.root != receipt.lens_root:
            return deny("FINITE_FORMAL_MHP_LENS_UNTRUSTED")
        check, replay = self.meaning_verifier.verify(lens)
        if check.status != "PASS" or replay != receipt:
            return deny("FINITE_FORMAL_MHP_REPLAY_FAILED")
        relation = self.relations.fetch_verified(relation_root)
        if (not isinstance(relation, ContextRelationReceiptV1)
                or relation.root != relation_root or relation.authority_class != NO_AUTHORITY):
            return deny("FINITE_FORMAL_RELATION_UNTRUSTED")
        source = sorted(
            (r for r in lens.readings if r.context_root == relation.source_context_root),
            key=lambda r: r.reading_id,
        )
        target = sorted(
            (r for r in lens.readings if r.context_root == relation.target_context_root),
            key=lambda r: r.reading_id,
        )
        if (not source or not target or len(source) > MAX_READINGS_PER_CONTEXT
                or len(target) > MAX_READINGS_PER_CONTEXT):
            return deny("FINITE_FORMAL_CONTEXT_FIBERS_INVALID")
        truth: dict[str, int] = {}
        roots: list[str] = []
        expected_vars: tuple[str, ...] | None = None
        for reading in (*source, *target):
            binding = self.bindings.fetch_verified(reading.context_binding_receipt_root)
            if (not isinstance(binding, ContextBindingReceiptV1)
                    or binding.root != reading.context_binding_receipt_root
                    or binding.authority_class != NO_AUTHORITY
                    or binding.reading_id != reading.reading_id
                    or binding.holon_root != lens.holon.root
                    or binding.occurrence_root != lens.occurrence.root
                    or binding.context_root != reading.context_root
                    or binding.envelope_root != reading.envelope_root):
                return deny("FINITE_FORMAL_CONTEXT_BINDING_UNTRUSTED")
            raw = self.artifacts.fetch_verified(binding.derived_root)
            if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != binding.derived_root:
                return deny("FINITE_FORMAL_ARTIFACT_UNTRUSTED")
            try:
                formula = parse_formal_reading(raw)
            except FiniteBooleanError as exc:
                return deny(str(exc))
            if expected_vars is None:
                expected_vars = formula.variables
            elif formula.variables != expected_vars:
                return deny("FINITE_FORMAL_VARIABLE_UNIVERSE_MISMATCH")
            if reading.reading_id in truth:
                return deny("FINITE_FORMAL_READING_ID_DUPLICATE")
            truth[reading.reading_id] = finite_truth_mask(formula)
            roots.append(formula.artifact_root)
        assert expected_vars is not None
        expected_pairs = tuple(sorted(
            (a.reading_id, b.reading_id)
            for a in source for b in target
            if truth[a.reading_id] & truth[b.reading_id]
        ))
        if expected_pairs != tuple(sorted(relation.allowed_reading_id_pairs)):
            return deny("FINITE_FORMAL_RELATION_TABLE_MISMATCH")
        masks = tuple(sorted(
            (name, f"{value:064x}") for name, value in truth.items()
        ))
        verification_root = canonical_hash(DOM_FINITE_TRUTH_CHECK, {
            "meaning_receipt_root": receipt.root,
            "relation_receipt_root": relation.root,
            "verified_formal_artifact_roots": sorted(roots),
            "reading_truth_masks_hex": masks,
            "valuation_count": 1 << len(expected_vars),
            "checked_pair_count": len(source) * len(target),
            "compatible_pair_count": len(expected_pairs),
            "incompatible_pair_count": len(source) * len(target) - len(expected_pairs),
            "status": PASS,
        })
        certificate = FiniteFormalRelationReceiptV1(
            receipt.root, relation.root, tuple(sorted(roots)), masks,
            1 << len(expected_vars), len(source)*len(target),
            len(expected_pairs), len(source)*len(target)-len(expected_pairs),
            verification_root,
        )
        return FiniteFormalRelationVerificationV1(PASS, (), verification_root), certificate
