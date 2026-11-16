"""Native, evidence-bound finite GLOBAL Boolean semantics falsifiers.

These tests replay genuine local MHP and complete two-context truth-table
verification; they do not model ordinary language or the category-theoretic
global-section obligations of the private Indexed Semantic Systems research.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import replace

import pytest

from harness.sdk.holon_finite_global_model import (
    DENIED, SAT, UNSAT, FiniteGlobalModelVerifierV1,
)
from harness.sdk.holon_indexed_context import (
    ContextRelationReceiptV1,
    IndexedContextProblemV1,
    IndexedContextVerifierV1,
    PASS as INDEX_PASS,
)
from harness.tests.test_holon_finite_semantics import (
    constant, formal, make_case, neg, var,
)
from harness.tests.test_holon_indexed_context import Store, h
from harness.sdk.holon_finite_semantics import finite_truth_mask, parse_formal_reading


def create_graph(expressions, variables=("p", "q")):
    c = make_case(expressions, variables)
    contexts = c["context"]
    assert set(contexts) == {"left", "right", "third"}
    reading_by_side = {}
    masks = {}
    for reading in c["lens"].readings:
        side = reading.reading_id.split("-", 1)[0]
        reading_by_side[side] = reading
        binding = c["bindings"].fetch_verified(reading.context_binding_receipt_root)
        raw = c["artifacts"].fetch_verified(binding.derived_root)
        parsed = parse_formal_reading(raw)
        assert parsed.variables == variables
        masks[side] = finite_truth_mask(parsed)
    assert set(masks) == set(contexts)
    links = [c["relation"]]
    for left, right in (("left", "third"), ("right", "third")):
        relation = c["relations"].put(ContextRelationReceiptV1(
            source_context_root=contexts[left],
            target_context_root=contexts[right],
            allowed_reading_id_pairs=(
                ((reading_by_side[left].reading_id, reading_by_side[right].reading_id),)
                if masks[left] & masks[right] else ()
            ),
            verifier_root=h("GLOBAL_FIXTURE_RELATION_VERIFIER", (left, right)),
            policy_root=h("GLOBAL_FIXTURE_RELATION_POLICY", (left, right)),
        ))
        links.append(relation)
    problem_store = Store()
    problem = problem_store.put(IndexedContextProblemV1(
        c["receipt"].root, tuple(relation.root for relation in links),
    ))
    indexed = IndexedContextVerifierV1(
        problems=problem_store,
        relations=c["relations"],
        receipts=c["receipts"],
        lenses=c["lenses"],
        meaning_verifier=c["verifier"].meaning_verifier,
    )
    global_verifier = FiniteGlobalModelVerifierV1(indexed=indexed, formal=c["verifier"])
    return {"global": global_verifier, "indexed": indexed, "problem": problem,
            "problem_store": problem_store, "links": links, "case": c, "masks": masks}


def assert_denied(graph, code):
    result, proof = graph["global"].verify(graph["problem"].root)
    assert result.status == DENIED
    assert result.error_codes == (code,)
    assert result.verification_root is None
    assert proof is None


@pytest.fixture
def triangle():
    return create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-notboth": neg({"op": "and", "args": [var("p"), var("q")]}),
    })


def test_each_pair_satisfiable_but_three_contexts_no_common_model(triangle):
    graph = triangle
    pair_outcome, _ = graph["indexed"].verify(graph["problem"].root)
    assert pair_outcome.status == INDEX_PASS
    assert all(len(link.allowed_reading_id_pairs) == 1 for link in graph["links"])
    for link in graph["links"]:
        status, proof = graph["case"]["verifier"].verify(
            graph["case"]["receipt"].root, link.root,
        )
        assert status.status == "PASS_EXHAUSTIVE_FORMAL_RELATION_ONLY"
        assert proof is not None and proof.compatible_pair_count == 1
        assert proof.incompatible_pair_count == 0
    result, certificate = graph["global"].verify(graph["problem"].root)
    assert result.status == UNSAT and result.error_codes == ()
    assert certificate is not None and certificate.authority_class == "NONE"
    assert certificate.model_kind == UNSAT and certificate.valuation_index is None
    assert certificate.selected_readings == ()
    assert certificate.variables == ("p", "q")
    assert certificate.valuation_count == 4
    assert len(certificate.verified_relation_receipt_roots) == 3
    assert len(certificate.verified_formal_relation_proof_roots) == 3
    assert len(certificate.verified_formal_artifact_roots) == 3
    assert result.verification_root == certificate.verification_root
    assert (result, certificate) == graph["global"].verify(graph["problem"].root)


def test_three_contexts_with_common_model_admit_exact_valuation():
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    result, certificate = graph["global"].verify(graph["problem"].root)
    assert result.status == SAT
    assert certificate is not None and certificate.authority_class == "NONE"
    assert certificate.model_kind == SAT and certificate.valuation_index == 3
    assert len(certificate.selected_readings) == 3
    assert certificate.variables == ("p", "q")


def test_explicitly_false_third_context_yields_proven_finite_unsat():
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-false": constant(False),
    })
    outcome, _ = graph["indexed"].verify(graph["problem"].root)
    assert outcome.status == "NO_FINITE_ASSIGNMENT_RELATIVE_TO_ATTESTED_RELATIONS"
    result, proof = graph["global"].verify(graph["problem"].root)
    assert result.status == UNSAT and proof is not None
    assert proof.valuation_index is None and proof.valuation_count == 4


def test_missing_trusted_relation_fails_global_without_claiming_unsat(triangle):
    graph = triangle
    del graph["case"]["relations"].data[graph["links"][1].root]
    assert_denied(graph, "GLOBAL_INDEX_VERIFICATION_DENIED")


def test_missing_mhp_source_lineage_fails_global(triangle):
    graph = triangle
    graph["case"]["verifier"].meaning_verifier.heritage.data.clear()
    assert_denied(graph, "GLOBAL_INDEX_VERIFICATION_DENIED")


def test_extra_allowed_pair_not_proved_by_formal_truth_table_is_denied():
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-notboth": neg({"op":"and", "args":[var("p"), var("q")]}),
    })
    first = graph["links"][0]
    altered = graph["case"]["relations"].put(
        replace(first, allowed_reading_id_pairs=())
    )
    problem = graph["problem_store"].put(IndexedContextProblemV1(
        graph["case"]["receipt"].root,
        (altered.root, graph["links"][1].root, graph["links"][2].root),
    ))
    graph["problem"] = problem
    # The index may report NO_SOLUTION relative to declared tables. Formal
    # truth-table proof still must reject the altered table before UNSAT.
    assert_denied(graph, "GLOBAL_FORMAL_PAIR_TABLE_UNVERIFIED")


def test_missing_global_receipt_or_invalid_problem_root_fails_closed(triangle):
    graph = triangle
    graph["problem_store"].items.clear()
    assert_denied(graph, "GLOBAL_INDEX_PROBLEM_UNTRUSTED")
    result, proof = graph["global"].verify("malformed")
    assert result.status == DENIED
    assert result.error_codes == ("GLOBAL_PROBLEM_ROOT_INVALID",)
    assert proof is None


def test_altered_context_binding_breaks_original_mhp_lineage(triangle):
    graph = triangle
    reading = graph["case"]["lens"].readings[0]
    binding = graph["case"]["bindings"].fetch_verified(
        reading.context_binding_receipt_root
    )
    graph["case"]["bindings"].data[binding.root] = replace(
        binding, occurrence_root="0" * 64,
    )
    assert_denied(graph, "GLOBAL_INDEX_VERIFICATION_DENIED")


def test_transplanted_formula_bytes_cannot_reuse_original_digest(triangle):
    graph = triangle
    reading = graph["case"]["lens"].readings[0]
    binding = graph["case"]["bindings"].fetch_verified(
        reading.context_binding_receipt_root
    )
    graph["case"]["artifacts"].data[binding.derived_root] = b"tampered"
    assert_denied(graph, "GLOBAL_INDEX_VERIFICATION_DENIED")


def test_different_variable_universes_cannot_create_common_model():
    # Original MHP is valid, and the declared graph is well-shaped, but one
    # context's formula belongs to an independently named logical universe.
    c = make_case({
        "left-p": formal(var("p"), ("p",)),
        "right-q": formal(var("q"), ("q",)),
        "third-true": formal(constant(True), ("p",)),
    }, ("p",))
    problem_store = Store()
    relation_store = c["relations"]
    # Explicitly bind the third context to the finite problem too.
    first = c["relation"]
    links = [first]
    for side in ("left", "right"):
        r = relation_store.put(ContextRelationReceiptV1(
            source_context_root=c["context"][side],
            target_context_root=c["context"]["third"],
            allowed_reading_id_pairs=(),
            verifier_root=h("VAR_UNIVERSE_RELATION", side),
            policy_root=h("VAR_UNIVERSE_POLICY", side),
        ))
        links.append(r)
    problem = problem_store.put(IndexedContextProblemV1(
        c["receipt"].root, tuple(r.root for r in links),
    ))
    indexed = IndexedContextVerifierV1(
        problems=problem_store, relations=relation_store,
        receipts=c["receipts"], lenses=c["lenses"],
        meaning_verifier=c["verifier"].meaning_verifier,
    )
    verifier = FiniteGlobalModelVerifierV1(indexed=indexed, formal=c["verifier"])
    outcome, proof = verifier.verify(problem.root)
    assert outcome.status == DENIED
    assert outcome.error_codes == ("GLOBAL_FORMAL_PAIR_TABLE_UNVERIFIED",)
    assert proof is None


def test_independent_exhaustive_valuations_match_global_verifier_on_80_triangles():
    """Separate formula evaluator is the independent, bounded model oracle."""
    rng = random.Random(20261116)

    def random_tree(depth):
        if depth <= 0 or rng.random() < 0.43:
            return rng.choice([var("p"), var("q"), constant(True), constant(False)])
        op = rng.choice(["not", "and", "or"])
        if op == "not":
            return {"op": op, "arg": random_tree(depth - 1)}
        return {"op": op, "args": [random_tree(depth - 1), random_tree(depth - 1)]}

    def eval_independent(tree, assignment):
        op = tree["op"]
        if op == "const":
            return bool(tree["value"])
        if op == "var":
            return assignment[tree["name"]]
        if op == "not":
            return not eval_independent(tree["arg"], assignment)
        values = [eval_independent(x, assignment) for x in tree["args"]]
        return all(values) if op == "and" else any(values)

    for trial in range(80):
        a, b, c = (random_tree(3), random_tree(3), random_tree(3))
        expected = any(
            all(eval_independent(tree, {"p": p, "q": q}) for tree in (a, b, c))
            for p, q in itertools.product((False, True), repeat=2)
        )
        graph = create_graph({
            f"left-r{trial}": a,
            f"right-r{trial}": b,
            f"third-r{trial}": c,
        })
        result, receipt = graph["global"].verify(graph["problem"].root)
        assert result.status == (SAT if expected else UNSAT), f"trial {trial}"
        assert receipt is not None and receipt.authority_class == "NONE"
        if expected:
            assert receipt.valuation_index is not None
        else:
            assert receipt.valuation_index is None
