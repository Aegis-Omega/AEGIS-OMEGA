"""Separate finite-Boolean certificate checker for AEGIS holonic contexts.

This checker intentionally does NOT call FiniteGlobalModelVerifierV1.verify,
FiniteFormalRelationVerifierV1.verify or finite_truth_mask. It independently
interprets the bounded Boolean AST and reconstructs every complete pair
relation and the final global receipt from exact MHP-bound source bytes.

It DOES reuse the exact canonical formula parser, existing MHP provenance
verifier, index structural verifier and canonical hash format. Thus the
independence is at the finite semantic calculation layer, not the provenance,
formal syntax or cryptographic implementation layers.

A matching certificate establishes only correctness within the declared
finite Boolean model and currently trusted stores, never fidelity to human
intent, a categorical global-section theorem or execution authority.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Protocol

from harness.sdk.holon_finite_global_model import (
    DENIED, DOMAIN_CHECK, SAT, UNSAT, FiniteGlobalModelReceiptV1,
    MAX_CONTEXTS, MAX_READINGS, MAX_RELATIONS,
)
from harness.sdk.holon_finite_semantics import (
    DOM_FINITE_TRUTH_CHECK, PASS as FORMAL_PASS, FiniteBooleanError,
    FiniteFormalRelationReceiptV1, FiniteFormalRelationVerifierV1,
    parse_formal_reading,
)
from harness.sdk.holon_indexed_context import (
    DENIED as INDEX_DENIED, IndexedContextProblemV1,
    IndexedContextVerifierV1,
)
from harness.sdk.holon_meaning_bridge import (
    ContextBindingReceiptV1, HolonMeaningLensV1, HolonMeaningReceiptV1,
)
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash, require_hash

CHECK_PASS = "PASS_INDEPENDENT_FINITE_BOOLEAN_CERTIFICATE_ONLY"
CHECK_DENIED = "FAIL_INDEPENDENT_FINITE_CERTIFICATE_DENIED"


class TrustedFiniteGlobalCertificateStore(Protocol):
    def fetch_verified(self, root: str) -> FiniteGlobalModelReceiptV1 | None: ...


@dataclass(frozen=True)
class FiniteCertificateCheckV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


def _eval_independent(node: dict, valuation: dict[str, bool]) -> bool:
    """Independent recursive evaluator. Input is validated by source parser."""
    op = node["op"]
    if op == "var":
        return valuation[node["name"]]
    if op == "const":
        return node["value"] is True
    if op == "not":
        return not _eval_independent(node["arg"], valuation)
    if op == "and":
        result = True
        for arg in node["args"]:
            result = result and _eval_independent(arg, valuation)
        return result
    if op == "or":
        result = False
        for arg in node["args"]:
            result = result or _eval_independent(arg, valuation)
        return result
    raise ValueError("UNSUPPORTED_FORMULA_OPERATOR")


class IndependentFiniteCertificateCheckerV1:
    """Read-only independently computed SAT/UNSAT receipt validation."""

    def __init__(
        self, *, certificates: TrustedFiniteGlobalCertificateStore,
        indexed: IndexedContextVerifierV1,
        formal: FiniteFormalRelationVerifierV1,
    ) -> None:
        self.certificates = certificates
        self.indexed = indexed
        self.formal = formal

    def verify(
        self, certificate_root: str
    ) -> tuple[FiniteCertificateCheckV1, FiniteGlobalModelReceiptV1 | None]:
        def deny(reason: str):
            return FiniteCertificateCheckV1(CHECK_DENIED, (reason,), None), None

        try:
            require_hash("certificate_root", certificate_root)
        except (ValueError, TypeError):
            return deny("FINITE_CERTIFICATE_ROOT_INVALID")
        cert = self.certificates.fetch_verified(certificate_root)
        if (not isinstance(cert, FiniteGlobalModelReceiptV1)
                or cert.root != certificate_root
                or cert.authority_class != NO_AUTHORITY):
            return deny("FINITE_CERTIFICATE_UNTRUSTED")

        problem = self.indexed.problems.fetch_verified(cert.problem_root)
        if (not isinstance(problem, IndexedContextProblemV1)
                or problem.root != cert.problem_root
                or problem.meaning_receipt_root != cert.meaning_receipt_root):
            return deny("FINITE_CERTIFICATE_SCOPE_MISMATCH")
        index_check, _ = self.indexed.verify(problem.root)
        if index_check.status == INDEX_DENIED or index_check.status not in (
            "PASS_FINITE_COMPATIBILITY_ONLY",
            "NO_FINITE_ASSIGNMENT_RELATIVE_TO_ATTESTED_RELATIONS",
            "OPEN_FINITE_SEARCH_BUDGET",
        ):
            return deny("FINITE_CERTIFICATE_INDEX_UNTRUSTED")

        mhp = self.formal.meanings.fetch_verified(problem.meaning_receipt_root)
        if (not isinstance(mhp, HolonMeaningReceiptV1)
                or mhp.root != problem.meaning_receipt_root
                or mhp.authority_class != NO_AUTHORITY):
            return deny("FINITE_CERTIFICATE_MHP_UNTRUSTED")
        lens = self.formal.lenses.fetch_verified(mhp.lens_root)
        if not isinstance(lens, HolonMeaningLensV1) or lens.root != mhp.lens_root:
            return deny("FINITE_CERTIFICATE_LENS_UNTRUSTED")
        mhp_check, mhp_replay = self.formal.meaning_verifier.verify(lens)
        if mhp_check.status != "PASS" or mhp_replay != mhp:
            return deny("FINITE_CERTIFICATE_MHP_NOT_REPLAYABLE")

        context_set = {r.context_root for r in lens.readings}
        if (not 2 <= len(context_set) <= MAX_CONTEXTS
                or not 1 <= len(lens.readings) <= MAX_READINGS
                or not 1 <= len(problem.relation_receipt_roots) <= MAX_RELATIONS):
            return deny("FINITE_CERTIFICATE_CONTEXT_SCOPE_INVALID")

        groups = defaultdict(list)
        formulas = {}
        artifact_roots = {}
        variables = None
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
                return deny("FINITE_CERTIFICATE_CONTEXT_BINDING_UNTRUSTED")
            data = self.formal.artifacts.fetch_verified(binding.derived_root)
            if not isinstance(data, bytes) or hashlib.sha256(data).hexdigest() != binding.derived_root:
                return deny("FINITE_CERTIFICATE_ARTIFACT_BYTES_UNTRUSTED")
            try:
                parsed = parse_formal_reading(data)
            except FiniteBooleanError:
                return deny("FINITE_CERTIFICATE_FORMULA_INVALID")
            if variables is None:
                variables = parsed.variables
            elif variables != parsed.variables:
                return deny("FINITE_CERTIFICATE_UNIVERSE_MISMATCH")
            if reading.reading_id in formulas:
                return deny("FINITE_CERTIFICATE_READING_DUPLICATE")
            groups[reading.context_root].append(reading.reading_id)
            formulas[reading.reading_id] = parsed.formula
            artifact_roots[reading.reading_id] = parsed.artifact_root
        if variables is None or set(groups) != context_set:
            return deny("FINITE_CERTIFICATE_READINGS_INCOMPLETE")

        ordered_contexts = tuple(sorted(groups))
        for ctx in ordered_contexts:
            groups[ctx].sort()
        valuation_count = 2 ** len(variables)
        # This is independent direct valuation enumeration; there is no
        # reference to producer's truth-mask or global-model implementation.
        values = {}
        for name, tree in formulas.items():
            mask = 0
            for index in range(valuation_count):
                assignment = {
                    variable: bool((index // (2 ** slot)) % 2)
                    for slot, variable in enumerate(variables)
                }
                if _eval_independent(tree, assignment):
                    mask += 2 ** index
            values[name] = mask

        formal_roots = []
        relation_roots = []
        relations = []
        for root in sorted(problem.relation_receipt_roots):
            rel = self.formal.relations.fetch_verified(root)
            if (rel is None or rel.root != root
                    or rel.authority_class != NO_AUTHORITY
                    or rel.source_context_root not in groups
                    or rel.target_context_root not in groups):
                return deny("FINITE_CERTIFICATE_RELATION_UNTRUSTED")
            left = groups[rel.source_context_root]
            right = groups[rel.target_context_root]
            pairs = tuple(sorted(
                (a, b)
                for a in left for b in right
                if (values[a] & values[b]) != 0
            ))
            if pairs != tuple(sorted(rel.allowed_reading_id_pairs)):
                return deny("FINITE_CERTIFICATE_PAIR_TABLE_INCORRECT")

            members = sorted(left + right)
            roots = tuple(sorted(artifact_roots[name] for name in members))
            masks = tuple(sorted((name, f"{values[name]:064x}") for name in members))
            checked = len(left) * len(right)
            check_root = canonical_hash(DOM_FINITE_TRUTH_CHECK, {
                "meaning_receipt_root": mhp.root,
                "relation_receipt_root": rel.root,
                "verified_formal_artifact_roots": list(roots),
                "reading_truth_masks_hex": masks,
                "valuation_count": valuation_count,
                "checked_pair_count": checked,
                "compatible_pair_count": len(pairs),
                "incompatible_pair_count": checked - len(pairs),
                "status": FORMAL_PASS,
            })
            proof = FiniteFormalRelationReceiptV1(
                mhp.root, rel.root, roots, masks, valuation_count,
                checked, len(pairs), checked - len(pairs), check_root,
            )
            formal_roots.append(proof.root)
            relation_roots.append(rel.root)
            relations.append(rel)

        # Context-level alternatives are not collapsed. Every possible
        # selected reading retains its exact original context and MHP identity.
        local_unions = []
        combined = (2 ** valuation_count) - 1
        for ctx in ordered_contexts:
            ctx_mask = 0
            for reading_id in groups[ctx]:
                ctx_mask |= values[reading_id]
            local_unions.append((ctx, f"{ctx_mask:064x}"))
            combined &= ctx_mask

        model_kind = SAT if combined else UNSAT
        shared = combined.bit_count()
        least = next((idx for idx in range(valuation_count) if combined & (1 << idx)), None)
        selected = ()
        if least is not None:
            selected = tuple(
                (ctx, next(name for name in groups[ctx] if values[name] & (1 << least)))
                for ctx in ordered_contexts
            )
            mapping = dict(selected)
            if any(
                (mapping[r.source_context_root], mapping[r.target_context_root])
                not in r.allowed_reading_id_pairs for r in relations
            ):
                return deny("FINITE_CERTIFICATE_RELATION_MODEL_INCOHERENT")

        relation_roots = tuple(sorted(relation_roots))
        formal_roots = tuple(sorted(formal_roots))
        unique_artifacts = tuple(sorted(set(artifact_roots.values())))
        per_context = tuple(local_unions)
        mask_hex = f"{combined:064x}"
        expected_check_root = canonical_hash(DOMAIN_CHECK, {
            "problem_root": problem.root,
            "meaning_receipt_root": mhp.root,
            "verified_relation_receipt_roots": relation_roots,
            "verified_formal_relation_proof_roots": formal_roots,
            "verified_formal_artifact_roots": unique_artifacts,
            "variables": variables,
            "valuation_count": valuation_count,
            "context_truth_union_masks_hex": per_context,
            "global_truth_mask_hex": mask_hex,
            "shared_valuation_count": shared,
            "model_kind": model_kind,
            "valuation_index": least,
            "selected_readings": selected,
        })
        expected = FiniteGlobalModelReceiptV1(
            problem.root, mhp.root, relation_roots, formal_roots,
            unique_artifacts, variables, valuation_count, per_context,
            mask_hex, shared, model_kind, least, selected,
            expected_check_root,
        )
        if expected != cert or expected.root != certificate_root:
            return deny("FINITE_CERTIFICATE_SEMANTIC_CONTENT_MISMATCH")
        return FiniteCertificateCheckV1(CHECK_PASS, (), expected_check_root), cert
