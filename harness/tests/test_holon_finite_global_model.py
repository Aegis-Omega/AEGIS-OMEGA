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
    reading_by_side = {side: [] for side in contexts}
    masks = {}
    for reading in c["lens"].readings:
        side = reading.reading_id.split("-", 1)[0]
        reading_by_side[side].append(reading)
        binding = c["bindings"].fetch_verified(reading.context_binding_receipt_root)
        raw = c["artifacts"].fetch_verified(binding.derived_root)
        parsed = parse_formal_reading(raw)
        assert parsed.variables == variables
        masks[reading.reading_id] = finite_truth_mask(parsed)
    assert all(reading_by_side.values())
    links = [c["relation"]]
    for left, right in (("left", "third"), ("right", "third")):
        relation = c["relations"].put(ContextRelationReceiptV1(
            source_context_root=contexts[left],
            target_context_root=contexts[right],
            allowed_reading_id_pairs=tuple(sorted(
                (a.reading_id, b.reading_id)
                for a in reading_by_side[left]
                for b in reading_by_side[right]
                if masks[a.reading_id] & masks[b.reading_id]
            )),
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
    assert certificate.shared_valuation_count == 0
    assert certificate.global_truth_mask_hex == "0" * 64
    assert len(certificate.context_truth_union_masks_hex) == 3
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
    assert certificate.shared_valuation_count == 1
    assert certificate.global_truth_mask_hex == f"{8:064x}"
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
        oracle_mask = sum(
            1 << i for i in range(4)
            if all(
                eval_independent(tree, {"p": bool(i & 1), "q": bool(i & 2)})
                for tree in (a, b, c)
            )
        )
        assert receipt.global_truth_mask_hex == f"{oracle_mask:064x}", f"trial {trial}"
        assert receipt.shared_valuation_count == oracle_mask.bit_count(), f"trial {trial}"
        assert len(receipt.context_truth_union_masks_hex) == 3
        if expected:
            assert receipt.valuation_index == (oracle_mask & -oracle_mask).bit_length() - 1
        else:
            assert receipt.valuation_index is None



def test_multireading_context_yields_witness_without_semantic_collapse():
    # Latin-origin interpretations in one holon/context remain alternatives.
    # Truth of p OR not-p spans every valuation, but neither alternative is
    # promoted to a universal interpretation of the original occurrence.
    graph = create_graph({
        "left-p": var("p"),
        "left-not-p": neg(var("p")),
        "right-q": var("q"),
        "third-notboth": neg({"op": "and", "args": [var("p"), var("q")]}),
    })
    index, _ = graph["indexed"].verify(graph["problem"].root)
    assert index.status == INDEX_PASS
    result, receipt = graph["global"].verify(graph["problem"].root)
    assert result.status == SAT and receipt is not None
    assert receipt.valuation_index == 2
    assert receipt.shared_valuation_count == 1
    assert receipt.global_truth_mask_hex == f"{4:064x}"
    chosen = dict(receipt.selected_readings)
    assert chosen[graph["case"]["context"]["left"]] == "left-not-p"
    assert chosen[graph["case"]["context"]["right"]] == "right-q"
    assert chosen[graph["case"]["context"]["third"]] == "third-notboth"
    local_masks = dict(receipt.context_truth_union_masks_hex)
    assert local_masks[graph["case"]["context"]["left"]] == f"{15:064x}"
    assert local_masks[graph["case"]["context"]["right"]] == f"{12:064x}"
    assert local_masks[graph["case"]["context"]["third"]] == f"{7:064x}"
    assert receipt.root and receipt.authority_class == "NONE"


def test_multiple_readings_can_leave_pairwise_solution_but_no_common_valuation():
    # Per-context alternatives do not rescue a globally impossible triple.
    # p and q can each overlap not(p and q), and p overlaps q; the three
    # formulas cannot all be true under a single valuation.
    graph = create_graph({
        "left-p": var("p"),
        "left-both": {"op": "and", "args": [var("p"), var("q")]},
        "right-q": var("q"),
        "third-notboth": neg({"op": "and", "args": [var("p"), var("q")]}),
    })
    index, witness = graph["indexed"].verify(graph["problem"].root)
    assert index.status == INDEX_PASS and witness is not None
    assert all(link.allowed_reading_id_pairs for link in graph["links"])
    result, receipt = graph["global"].verify(graph["problem"].root)
    assert result.status == UNSAT and receipt is not None
    assert receipt.shared_valuation_count == 0
    assert receipt.global_truth_mask_hex == "0" * 64
    assert receipt.valuation_index is None and receipt.selected_readings == ()
    assert len(receipt.context_truth_union_masks_hex) == 3


def test_every_global_valuer_is_bound_into_receipt_not_just_first_witness():
    # All 4 assignments satisfy the complete constant-true system; this
    # must be visible in the receipt instead of hidden behind witness 0.
    graph = create_graph({
        "left-true": constant(True),
        "right-true": constant(True),
        "third-true": constant(True),
    })
    result, receipt = graph["global"].verify(graph["problem"].root)
    assert result.status == SAT and receipt is not None
    assert receipt.shared_valuation_count == 4
    assert receipt.global_truth_mask_hex == f"{15:064x}"
    assert receipt.valuation_index == 0
    assert len(receipt.selected_readings) == 3
    assert all(v == f"{15:064x}" for _, v in receipt.context_truth_union_masks_hex)


def test_distinct_context_union_roots_cannot_be_confused():
    # Hash-bound receipts encode contexts, not just an anonymous multiset of
    # truth masks; provenance stays attached to the indexed context identity.
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    result, receipt = graph["global"].verify(graph["problem"].root)
    assert result.status == SAT and receipt is not None
    identities = tuple(ctx for ctx, _ in receipt.context_truth_union_masks_hex)
    assert identities == tuple(sorted(identities))
    assert set(identities) == set(graph["case"]["context"].values())
    assert len(set(identities)) == 3


def test_independent_multireading_oracle_on_64_randomized_three_context_graphs():
    """Separate interpreter exhaustively checks all readings and 2^2 valuations.

    The oracle deliberately does NOT consume the verifier's truth-mask helper,
    derived certificate or existing pair-table solver, so that a shared bug
    in either path cannot make the global result look correct.
    """
    rng = random.Random(20261116 + 812)
    sides = ("left", "right", "third")

    def generate(depth):
        if depth == 0 or rng.random() < 0.42:
            return rng.choice([var("p"), var("q"), constant(True), constant(False)])
        op = rng.choice(("not", "and", "or"))
        if op == "not":
            return {"op": "not", "arg": generate(depth - 1)}
        return {"op": op, "args": [generate(depth - 1), generate(depth - 1)]}

    def evaluate(tree, valuation):
        if tree["op"] == "const":
            return tree["value"]
        if tree["op"] == "var":
            return valuation[tree["name"]]
        if tree["op"] == "not":
            return not evaluate(tree["arg"], valuation)
        values = [evaluate(x, valuation) for x in tree["args"]]
        return (all(values) if tree["op"] == "and" else any(values))

    for trial in range(64):
        candidates = {
            side: (generate(3), generate(3))
            for side in sides
        }
        expressions = {
            f"{side}-r{slot}": tree
            for side, pair in candidates.items()
            for slot, tree in enumerate(pair)
        }
        graph = create_graph(expressions)
        result, proof = graph["global"].verify(graph["problem"].root)
        assert proof is not None and proof.authority_class == "NONE"
        oracle = 0
        local_masks = {side: 0 for side in sides}
        for index in range(4):
            valuation = {"p": bool(index & 1), "q": bool(index & 2)}
            satisfied = {}
            for side in sides:
                satisfied[side] = any(
                    evaluate(tree, valuation) for tree in candidates[side]
                )
                if satisfied[side]:
                    local_masks[side] |= 1 << index
            if all(satisfied.values()):
                oracle |= 1 << index
        assert result.status == (SAT if oracle else UNSAT), f"trial={trial}"
        assert proof.global_truth_mask_hex == f"{oracle:064x}", f"trial={trial}"
        assert proof.shared_valuation_count == oracle.bit_count(), f"trial={trial}"
        for source, hexdigest in proof.context_truth_union_masks_hex:
            side = next(side for side in sides if graph["case"]["context"][side] == source)
            assert hexdigest == f"{local_masks[side]:064x}", f"trial={trial}"
        if oracle:
            assert proof.valuation_index == (oracle & -oracle).bit_length() - 1
            selected = dict(proof.selected_readings)
            for side in sides:
                chosen = selected[graph["case"]["context"][side]]
                tree = expressions[chosen]
                assert evaluate(tree, {
                    "p": bool(proof.valuation_index & 1),
                    "q": bool(proof.valuation_index & 2),
                })
        else:
            assert proof.valuation_index is None
            assert proof.selected_readings == ()


def test_maximum_eight_variable_space_hashes_all_256_truth_values():
    # 256 valuation bits are represented by exactly 64 hexadecimal digits.
    variables = tuple("abcdefgh")
    graph = create_graph({
        "left-a": var("a"),
        "left-nota": neg(var("a")),
        "right-true": constant(True),
        "third-true": constant(True),
    }, variables=variables)
    result, proof = graph["global"].verify(graph["problem"].root)
    assert result.status == SAT and proof is not None
    assert proof.variables == variables
    assert proof.valuation_count == 256
    assert proof.shared_valuation_count == 256
    assert proof.global_truth_mask_hex == "f" * 64
    assert proof.valuation_index == 0
    assert proof.authority_class == "NONE"


def test_global_unsat_receipt_replay_preserves_original_evidence(triangle):
    from harness.sdk.holon_finite_global_model import FiniteGlobalReceiptReplayVerifierV1
    graph = triangle
    outcome, original = graph["global"].verify(graph["problem"].root)
    assert outcome.status == UNSAT and original is not None
    receipts = Store()
    receipts.put(original)
    replay = FiniteGlobalReceiptReplayVerifierV1(
        receipts=receipts, verifier=graph["global"]
    )
    assert replay.verify(original.root) == (outcome, original)
    assert original.shared_valuation_count == 0
    assert original.authority_class == "NONE"


def test_global_sat_receipt_replay_preserves_exact_witness():
    from harness.sdk.holon_finite_global_model import FiniteGlobalReceiptReplayVerifierV1
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    outcome, original = graph["global"].verify(graph["problem"].root)
    assert outcome.status == SAT and original is not None
    receipts = Store()
    receipts.put(original)
    verifier = FiniteGlobalReceiptReplayVerifierV1(
        receipts=receipts, verifier=graph["global"]
    )
    assert verifier.verify(original.root) == (outcome, original)
    assert original.valuation_index == 3


def test_global_replay_rejects_removed_prior_receipt(triangle):
    from harness.sdk.holon_finite_global_model import FiniteGlobalReceiptReplayVerifierV1
    graph = triangle
    _, original = graph["global"].verify(graph["problem"].root)
    assert original is not None
    store = Store()
    store.put(original)
    verifier = FiniteGlobalReceiptReplayVerifierV1(
        receipts=store, verifier=graph["global"]
    )
    del store.items[original.root]
    denied, result = verifier.verify(original.root)
    assert denied.status == DENIED
    assert denied.error_codes == ("GLOBAL_REPLAY_RECEIPT_UNTRUSTED",)
    assert result is None


def test_global_replay_rejects_swapped_proof_content(triangle):
    from harness.sdk.holon_finite_global_model import FiniteGlobalReceiptReplayVerifierV1
    graph = triangle
    _, original = graph["global"].verify(graph["problem"].root)
    assert original is not None
    store = Store()
    store.put(original)
    forged = replace(original, global_truth_mask_hex="f" * 64)
    store.items[original.root] = forged
    verifier = FiniteGlobalReceiptReplayVerifierV1(
        receipts=store, verifier=graph["global"]
    )
    denied, result = verifier.verify(original.root)
    assert denied.status == DENIED
    assert denied.error_codes == ("GLOBAL_REPLAY_RECEIPT_UNTRUSTED",)
    assert result is None


def test_global_replay_fails_closed_if_source_lineage_disappears(triangle):
    from harness.sdk.holon_finite_global_model import FiniteGlobalReceiptReplayVerifierV1
    graph = triangle
    _, original = graph["global"].verify(graph["problem"].root)
    assert original is not None
    store = Store()
    store.put(original)
    verifier = FiniteGlobalReceiptReplayVerifierV1(
        receipts=store, verifier=graph["global"]
    )
    graph["case"]["verifier"].meaning_verifier.heritage.data.clear()
    denied, result = verifier.verify(original.root)
    assert denied.status == DENIED
    assert denied.error_codes == ("GLOBAL_REPLAY_EVIDENCE_NO_LONGER_VALID",)
    assert result is None


def test_global_replay_fails_closed_when_formal_pair_evidence_is_removed(triangle):
    from harness.sdk.holon_finite_global_model import FiniteGlobalReceiptReplayVerifierV1
    graph = triangle
    _, original = graph["global"].verify(graph["problem"].root)
    assert original is not None
    store = Store()
    store.put(original)
    verifier = FiniteGlobalReceiptReplayVerifierV1(
        receipts=store, verifier=graph["global"]
    )
    del graph["case"]["relations"].data[graph["links"][1].root]
    denied, result = verifier.verify(original.root)
    assert denied.status == DENIED
    assert denied.error_codes == ("GLOBAL_REPLAY_EVIDENCE_NO_LONGER_VALID",)
    assert result is None


def test_global_replay_bad_root_does_not_turn_into_open_or_unsat(triangle):
    from harness.sdk.holon_finite_global_model import FiniteGlobalReceiptReplayVerifierV1
    graph = triangle
    verifier = FiniteGlobalReceiptReplayVerifierV1(
        receipts=Store(), verifier=graph["global"]
    )
    denied, result = verifier.verify("this-is-not-a-digest")
    assert denied.status == DENIED
    assert denied.error_codes == ("GLOBAL_REPLAY_ROOT_INVALID",)
    assert result is None
