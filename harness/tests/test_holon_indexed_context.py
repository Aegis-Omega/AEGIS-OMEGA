"""Finite indexed context falsifiers tied to native AEGIS MHP heritage receipts.

A compatible finite assignment does not certify global categorical sections,
natural transformations, scientific truths, language equivalence or authority.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from harness.sdk.holon_indexed_context import (
    ContextRelationReceiptV1,
    IndexedContextError,
    IndexedContextProblemV1,
    IndexedContextVerifierV1,
    MAX_COMBINATIONS,
    NO_SOLUTION,
    OPEN,
    PASS,
    solve_finite_fiber_constraints,
)
from harness.sdk.meaning_heritage import canonical_hash
from harness.tests.test_holon_meaning_bridge import example as existing_lens_example


def h(key: str, value: object) -> str:
    return canonical_hash(key, value)


class Store:
    def __init__(self):
        self.items = {}

    def put(self, value):
        self.items[value.root] = value
        return value

    def fetch_verified(self, root):
        return self.items.get(root)


@pytest.fixture
def case(existing_lens_example):
    lens, lineage_verifier, *_ = existing_lens_example
    check, receipt = lineage_verifier.verify(lens)
    assert check.status == "PASS" and receipt is not None
    a, b = lens.readings
    relation = ContextRelationReceiptV1(
        source_context_root=a.context_root,
        target_context_root=b.context_root,
        allowed_reading_id_pairs=((a.reading_id, b.reading_id),),
        verifier_root=h("TEST_CONTEXT_RELATION_VERIFIER", "v1"),
        policy_root=h("TEST_CONTEXT_RELATION_POLICY", "v1"),
    )
    problem = IndexedContextProblemV1(receipt.root, (relation.root,))
    problems, relations, receipts, lenses = Store(), Store(), Store(), Store()
    problems.put(problem)
    relations.put(relation)
    receipts.put(receipt)
    lenses.put(lens)
    verifier = IndexedContextVerifierV1(
        problems=problems, relations=relations, receipts=receipts,
        lenses=lenses, meaning_verifier=lineage_verifier,
    )
    return {
        "verifier": verifier, "lens": lens, "receipt": receipt,
        "relation": relation, "problem": problem,
        "problems": problems, "relations": relations,
        "receipts": receipts, "lenses": lenses,
    }


def test_two_explicitly_compatible_meanings_preserve_both_contexts(case):
    result, evidence = case["verifier"].verify(case["problem"].root)
    assert result.status == PASS and result.error_codes == ()
    assert evidence is not None and evidence.authority_class == "NONE"
    assert evidence.meaning_receipt_root == case["receipt"].root
    assert evidence.relation_receipt_roots == (case["relation"].root,)
    assert evidence.search_space_bound == 1
    assert set(evidence.selected_readings) == {
        (r.context_root, r.reading_id) for r in case["lens"].readings
    }
    assert evidence.verification_root == result.verification_root
    assert case["verifier"].verify(case["problem"].root) == (result, evidence)


def test_no_explicit_allowed_pair_reports_relative_no_solution_not_truth(case):
    previous = case["relation"]
    forbidden = case["relations"].put(
        replace(previous, allowed_reading_id_pairs=())
    )
    problem = case["problems"].put(
        IndexedContextProblemV1(case["receipt"].root, (forbidden.root,))
    )
    result, evidence = case["verifier"].verify(problem.root)
    assert result.status == NO_SOLUTION
    assert result.error_codes == ("NO_ASSIGNMENT_FOR_ATTESTED_RELATIONS",)
    assert result.verification_root is None and evidence is None


def test_problem_without_cross_context_evidence_denied(case):
    problem = case["problems"].put(
        IndexedContextProblemV1(case["receipt"].root, ())
    )
    result, evidence = case["verifier"].verify(problem.root)
    assert result.error_codes == ("CONTEXT_INDEX_UNCONNECTED",)
    assert evidence is None


def test_genuine_meaning_receipt_is_not_replaced_by_attested_relation(case):
    case["receipts"].items.pop(case["receipt"].root)
    result, evidence = case["verifier"].verify(case["problem"].root)
    assert result.error_codes == ("MEANING_RECEIPT_UNTRUSTED",)
    assert evidence is None


def test_valid_looking_relation_not_in_trusted_store_fails_closed(case):
    case["relations"].items.clear()
    result, evidence = case["verifier"].verify(case["problem"].root)
    assert result.error_codes == ("RELATION_RECEIPT_UNTRUSTED",)
    assert evidence is None


def test_mutated_relation_cannot_reuse_old_attestation_root(case):
    rel = case["relation"]
    case["relations"].items[rel.root] = replace(rel, policy_root=h("DIFFERENT", "policy"))
    result, evidence = case["verifier"].verify(case["problem"].root)
    assert result.error_codes == ("RELATION_RECEIPT_UNTRUSTED",)
    assert evidence is None


def test_transplanted_context_not_present_in_lineage_is_denied(case):
    rel = replace(case["relation"], target_context_root=h("ALIEN_CONTEXT", 1))
    case["relations"].put(rel)
    problem = case["problems"].put(
        IndexedContextProblemV1(case["receipt"].root, (rel.root,))
    )
    result, evidence = case["verifier"].verify(problem.root)
    assert result.error_codes == ("CONSTRAINT_CONTEXT_INVALID",)
    assert evidence is None


def test_reading_id_transplanted_between_contexts_is_denied(case):
    a, b = case["lens"].readings
    rel = replace(case["relation"], allowed_reading_id_pairs=((b.reading_id, a.reading_id),))
    case["relations"].put(rel)
    problem = case["problems"].put(
        IndexedContextProblemV1(case["receipt"].root, (rel.root,))
    )
    result, evidence = case["verifier"].verify(problem.root)
    assert result.error_codes == ("CONSTRAINT_PAIR_NOT_IN_FIBERS",)
    assert evidence is None


def test_even_valid_sounding_hash_is_not_trusted_by_hash_alone(case):
    result, evidence = case["verifier"].verify("0" * 64)
    assert result.error_codes == ("PROBLEM_UNTRUSTED",)
    assert evidence is None


def test_missing_meaning_lens_denied(case):
    case["lenses"].items.clear()
    result, evidence = case["verifier"].verify(case["problem"].root)
    assert result.error_codes == ("MEANING_LENS_UNTRUSTED",)
    assert evidence is None


def test_pure_solver_genuine_nontrivial_finite_assignment():
    a, b = h("CONTEXT", "a"), h("CONTEXT", "b")
    fibers = ((b, ("0", "1")), (a, ("0", "1")))
    constraints = ((a, b, (("0", "0"), ("1", "1"))),)
    status, chosen, bound = solve_finite_fiber_constraints(fibers, constraints)
    assert status == PASS
    assert bound == 4
    assert chosen == ((a, "0"), (b, "0")) if a < b else chosen == ((b, "0"), (a, "0"))


def test_pairwise_satisfiable_triangle_can_have_no_global_assignment():
    # On a triangle, binary inequality is locally satisfiable on each edge;
    # there is no 2-colouring satisfying all three simultaneously.
    a, b, c = (h("CONTEXT", x) for x in ("a", "b", "c"))
    fibers = tuple((x, ("0", "1")) for x in (a, b, c))
    neq = (("0", "1"), ("1", "0"))
    constraints = ((a, b, neq), (b, c, neq), (c, a, neq))
    assert all(any(p[0] != p[1] for p in edge[2]) for edge in constraints)
    status, chosen, bound = solve_finite_fiber_constraints(fibers, constraints)
    assert status == NO_SOLUTION
    assert chosen is None and bound == 8


def test_order_independence_of_fiber_enumeration_and_relation_order():
    a, b, c = (h("CONTEXT", x) for x in ("one", "two", "three"))
    fibers = ((a, ("β", "α")), (b, ("β", "α")), (c, ("β", "α")))
    equality = (("α", "α"), ("β", "β"))
    relations = ((a, b, equality), (b, c, equality))
    first = solve_finite_fiber_constraints(fibers, relations)
    second = solve_finite_fiber_constraints(tuple(reversed(fibers)), tuple(reversed(relations)))
    assert first == second and first[0] == PASS


def test_large_cartesian_space_can_be_proved_sat_by_constraint_propagation():
    contexts = tuple(h("CONTEXT", str(i)) for i in range(12))
    fibers = tuple((ctx, tuple(str(v) for v in range(12))) for ctx in contexts)
    relations = tuple(
        (contexts[i], contexts[i + 1], tuple((str(v), str(v)) for v in range(12)))
        for i in range(11)
    )
    status, selected, bound = solve_finite_fiber_constraints(fibers, relations)
    assert status == PASS and selected is not None and bound > MAX_COMBINATIONS
    assignments = dict(selected)
    assert len(assignments) == len(contexts)
    assert all(assignments[a] == assignments[b] for a, b, _ in relations)


def test_small_search_budget_returns_open_only_after_structural_validation():
    a, b = h("CONTEXT", "budget-a"), h("CONTEXT", "budget-b")
    fibers = ((a, ("0", "1")), (b, ("0", "1")))
    relations = ((a, b, (("0", "0"), ("1", "1"))),)
    status, selected, bound = solve_finite_fiber_constraints(
        fibers, relations, max_search_nodes=1
    )
    assert status == OPEN and selected is None and bound == 4
    status2, selected2, bound2 = solve_finite_fiber_constraints(
        fibers, relations, max_search_nodes=2
    )
    assert status2 == PASS and selected2 is not None and bound2 == 4


@pytest.mark.parametrize("bad", (0, -1, True, 1.5, None))
def test_invalid_search_budget_rejected_without_computation(bad):
    a = h("CONTEXT", "bad-budget")
    with pytest.raises(IndexedContextError, match="SEARCH_NODE_BUDGET_INVALID"):
        solve_finite_fiber_constraints(((a, ("x",)),), (), max_search_nodes=bad)


def test_duplicate_constraints_fail_not_override_previous_relation():
    a, b = h("CONTEXT", "a"), h("CONTEXT", "b")
    fibers = ((a, ("x",)), (b, ("y",)))
    constraints = ((a, b, (("x", "y"),)), (a, b, ()))
    with pytest.raises(IndexedContextError, match="CONSTRAINT_EDGE_DUPLICATE"):
        solve_finite_fiber_constraints(fibers, constraints)


def test_disconnected_context_index_is_not_closed():
    a, b, c = (h("CONTEXT", x) for x in ("a", "b", "c"))
    fibers = ((a, ("x",)), (b, ("y",)), (c, ("z",)))
    with pytest.raises(IndexedContextError, match="CONTEXT_INDEX_UNCONNECTED"):
        solve_finite_fiber_constraints(fibers, ((a, b, (("x", "y"),)),))


def test_relation_receipt_rejects_malformed_pairs_and_self_links(case):
    rel = case["relation"]
    with pytest.raises(IndexedContextError, match="RELATION_SELF_CONTEXT"):
        replace(rel, target_context_root=rel.source_context_root)
    with pytest.raises(IndexedContextError, match="RELATION_PAIR_DUPLICATE"):
        replace(rel, allowed_reading_id_pairs=rel.allowed_reading_id_pairs * 2)
    with pytest.raises(IndexedContextError, match="RELATION_PAIR_INVALID"):
        replace(rel, allowed_reading_id_pairs=(("one", ""),))


def test_problem_root_is_order_invariant_for_relation_references(case):
    root_a, root_b = h("RELATION", "a"), h("RELATION", "b")
    a = IndexedContextProblemV1(case["receipt"].root, (root_a, root_b))
    b = IndexedContextProblemV1(case["receipt"].root, (root_b, root_a))
    assert a.root == b.root


def test_empty_syntactic_fiber_rejected():
    ctx = h("CTX", "zero")
    with pytest.raises(IndexedContextError, match="FIBER_CHOICES_INVALID"):
        solve_finite_fiber_constraints(((ctx, ()),), ())


def test_overly_many_relation_claims_fail_closed(case):
    rel = case["relation"]
    with pytest.raises(IndexedContextError, match="RELATION_PAIRS_INVALID"):
        replace(rel, allowed_reading_id_pairs=tuple((str(i), "id") for i in range(145)))


def test_oversized_disconnected_index_is_denied_before_open_budget():
    contexts = tuple(h("OVERSIZED_CONTEXT", i) for i in range(12))
    fibers = tuple((ctx, tuple(str(v) for v in range(12))) for ctx in contexts)
    # 12^12 assignments exceed the budget, but a missing index link is a
    # structural failure, not "unknown due to budget".
    with pytest.raises(IndexedContextError, match="CONTEXT_INDEX_UNCONNECTED"):
        solve_finite_fiber_constraints(fibers, ())


def test_oversized_invalid_relation_is_denied_before_open_budget():
    contexts = tuple(h("OVERSIZED_CONTEXT", i) for i in range(12))
    fibers = tuple((ctx, tuple(str(v) for v in range(12))) for ctx in contexts)
    relations = tuple(
        (contexts[i], contexts[i + 1], (("0", "0"),))
        for i in range(11)
    )
    bad = relations[:-1] + ((contexts[10], contexts[11], (("0", "not-a-reading"),)),)
    with pytest.raises(IndexedContextError, match="CONSTRAINT_PAIR_NOT_IN_FIBERS"):
        solve_finite_fiber_constraints(fibers, bad)


def test_oversized_malformed_relation_pair_cannot_hide_behind_open():
    contexts = tuple(h("OVERSIZED_CONTEXT", i) for i in range(12))
    fibers = tuple((ctx, tuple(str(v) for v in range(12))) for ctx in contexts)
    relations = tuple(
        (contexts[i], contexts[i + 1], (("0", "0"),))
        for i in range(11)
    )
    bad = relations[:-1] + ((contexts[10], contexts[11], (("0",),)),)
    with pytest.raises(IndexedContextError, match="CONSTRAINT_PAIR_INVALID"):
        solve_finite_fiber_constraints(fibers, bad)


def test_oversized_duplicate_edge_is_denied_before_open_budget():
    contexts = tuple(h("OVERSIZED_CONTEXT", i) for i in range(12))
    fibers = tuple((ctx, tuple(str(v) for v in range(12))) for ctx in contexts)
    relations = tuple(
        (contexts[i], contexts[i + 1], (("0", "0"),))
        for i in range(11)
    )
    with pytest.raises(IndexedContextError, match="CONSTRAINT_EDGE_DUPLICATE"):
        solve_finite_fiber_constraints(fibers, relations + (relations[0],))


def test_wrong_relation_record_shape_fails_as_structured_denial():
    a, b = h("CONTEXT", "shape-a"), h("CONTEXT", "shape-b")
    fibers = ((a, ("0",)), (b, ("1",)))
    with pytest.raises(IndexedContextError, match="CONSTRAINT_RECORD_INVALID"):
        solve_finite_fiber_constraints(fibers, ((a, b),))


def test_wrong_fiber_record_shape_fails_as_structured_denial():
    ctx = h("CONTEXT", "shape")
    with pytest.raises(IndexedContextError, match="FIBER_RECORD_INVALID"):
        solve_finite_fiber_constraints(((ctx,),), ())


def test_new_csp_matches_independent_exhaustive_oracle_on_250_small_graphs():
    # The oracle does NOT call the new pruning/search algorithm. It enumerates
    # all assignments directly over finite domains; its result checks the
    # whole solver, not a shared implementation detail.
    import itertools
    import random

    rng = random.Random(20261116)
    for trial in range(250):
        count = rng.randint(2, 4)
        contexts = tuple(h("ORACLE_CONTEXT", [trial, idx]) for idx in range(count))
        options = {
            ctx: tuple(str(i) for i in range(rng.randint(1, 3)))
            for ctx in contexts
        }
        edges = [(i, i + 1) for i in range(count - 1)]
        edges.extend(
            (i, j) for i in range(count) for j in range(i + 2, count)
            if rng.choice((True, False))
        )
        constraints = []
        for i, j in edges:
            a, b = contexts[i], contexts[j]
            pairs = tuple(
                (x, y) for x in options[a] for y in options[b]
                if rng.random() < 0.48
            )
            constraints.append((a, b, pairs))
        rng.shuffle(constraints)
        fibers = list(options.items())
        rng.shuffle(fibers)
        status, candidate, bound = solve_finite_fiber_constraints(
            tuple(fibers), tuple(constraints)
        )
        ordered = tuple(sorted(contexts))
        exhaustive = [
            dict(zip(ordered, vals))
            for vals in itertools.product(*(options[ctx] for ctx in ordered))
            if all(
                (dict(zip(ordered, vals))[a], dict(zip(ordered, vals))[b]) in pairs
                for a, b, pairs in constraints
            )
        ]
        assert bound == len(list(itertools.product(*(options[ctx] for ctx in ordered))))
        assert (status == PASS) == bool(exhaustive), f"trial={trial}"
        assert status != OPEN, f"unexpected budget exhaustion trial={trial}"
        if candidate is None:
            assert status == NO_SOLUTION and not exhaustive, f"trial={trial}"
        else:
            assert dict(candidate) in exhaustive, f"invalid witness trial={trial}"


def test_pruning_proves_global_no_solution_with_enough_budget():
    # Equality on two links and inequality on the third is inconsistent.
    a, b, c = (h("CONTEXT", x) for x in ("s1", "s2", "s3"))
    fibers = tuple((x, ("0", "1")) for x in (a, b, c))
    eq = (("0", "0"), ("1", "1"))
    neq = (("0", "1"), ("1", "0"))
    rels = ((a, b, eq), (b, c, eq), (c, a, neq))
    status, witness, bound = solve_finite_fiber_constraints(
        fibers, rels, max_search_nodes=100
    )
    assert status == NO_SOLUTION and witness is None and bound == 8


def test_budget_cannot_mask_invalid_cross_context_relation():
    a, b = h("CONTEXT", "bad-a"), h("CONTEXT", "bad-b")
    fibers = ((a, ("0", "1")), (b, ("0", "1")))
    with pytest.raises(IndexedContextError, match="CONSTRAINT_PAIR_NOT_IN_FIBERS"):
        solve_finite_fiber_constraints(
            fibers, ((a, b, (("0", "absent"),)),), max_search_nodes=1
        )
