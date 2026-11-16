"""Independent finite Boolean certificate verification, including fault injection.

This checker re-evaluates canonical MHP-derived Boolean formulas directly,
rather than replaying the same finite_truth_mask arithmetic as the producer.
The trust and original-intent boundaries remain explicit.
"""
from __future__ import annotations

from dataclasses import replace
import pytest

from harness.sdk.holon_finite_certificate_checker import (
    CHECK_DENIED, CHECK_PASS, IndependentFiniteCertificateCheckerV1,
)
from harness.sdk.holon_finite_global_model import DOMAIN_CHECK, SAT, UNSAT
from harness.sdk.meaning_heritage import canonical_hash
from harness.tests.test_holon_finite_global_model import create_graph, triangle
from harness.tests.test_holon_finite_semantics import constant, neg, var
from harness.tests.test_holon_indexed_context import Store


def with_checker(graph):
    producer_check, issued = graph["global"].verify(graph["problem"].root)
    assert producer_check.status in (SAT, UNSAT)
    assert issued is not None and issued.authority_class == "NONE"
    receipts = Store()
    receipts.put(issued)
    checker = IndependentFiniteCertificateCheckerV1(
        certificates=receipts,
        indexed=graph["indexed"],
        formal=graph["case"]["verifier"],
    )
    return checker, receipts, issued


def assert_denied(result, expected):
    check, certificate = result
    assert check.status == CHECK_DENIED
    assert check.error_codes == (expected,)
    assert check.verification_root is None and certificate is None


def test_independently_recomputed_global_unsat_certificate(triangle):
    checker, _, issued = with_checker(triangle)
    assert issued.model_kind == UNSAT
    check, certificate = checker.verify(issued.root)
    assert check.status == CHECK_PASS
    assert certificate == issued
    assert check.verification_root == issued.verification_root


def test_independently_recomputed_global_sat_certificate():
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    checker, _, issued = with_checker(graph)
    assert issued.model_kind == SAT
    check, certificate = checker.verify(issued.root)
    assert check.status == CHECK_PASS
    assert certificate == issued
    assert issued.valuation_index == 3
    assert issued.shared_valuation_count == 1


def test_independent_multireading_context_sat():
    graph = create_graph({
        "left-p": var("p"),
        "left-notp": neg(var("p")),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    checker, _, issued = with_checker(graph)
    check, certificate = checker.verify(issued.root)
    assert check.status == CHECK_PASS
    assert certificate == issued
    assert issued.shared_valuation_count == 2


def test_independent_full_256_valuations():
    graph = create_graph({
        "left-a": var("a"),
        "left-nota": neg(var("a")),
        "right-true": constant(True),
        "third-true": constant(True),
    }, variables=tuple("abcdefgh"))
    checker, _, issued = with_checker(graph)
    check, certificate = checker.verify(issued.root)
    assert check.status == CHECK_PASS
    assert certificate == issued
    assert issued.valuation_count == 256
    assert issued.shared_valuation_count == 256
    assert issued.global_truth_mask_hex == "f" * 64


def test_missing_prior_certificate_denied(triangle):
    checker, receipts, issued = with_checker(triangle)
    receipts.items.clear()
    assert_denied(
        checker.verify(issued.root), "FINITE_CERTIFICATE_UNTRUSTED"
    )


def test_malformed_certificate_root_denied(triangle):
    checker, _, _ = with_checker(triangle)
    assert_denied(
        checker.verify("not-a-valid-digest"),
        "FINITE_CERTIFICATE_ROOT_INVALID",
    )


def test_missing_mhp_evidence_denied_before_boolean_result(triangle):
    checker, _, issued = with_checker(triangle)
    triangle["case"]["verifier"].meaning_verifier.heritage.data.clear()
    assert_denied(
        checker.verify(issued.root), "FINITE_CERTIFICATE_INDEX_UNTRUSTED"
    )


def test_missing_authenticated_relation_denied_before_boolean_result(triangle):
    checker, _, issued = with_checker(triangle)
    del triangle["case"]["relations"].data[triangle["links"][0].root]
    assert_denied(
        checker.verify(issued.root), "FINITE_CERTIFICATE_INDEX_UNTRUSTED"
    )


def test_unchanged_old_root_cannot_hide_modified_content(triangle):
    checker, receipts, issued = with_checker(triangle)
    receipts.items[issued.root] = replace(
        issued, global_truth_mask_hex="f" * 64
    )
    assert_denied(
        checker.verify(issued.root), "FINITE_CERTIFICATE_UNTRUSTED"
    )


def _reissue_forgery(original, **modifications):
    """Create a syntactically self-consistent forged receipt, not just a bad hash.

    The independent checker must defeat a completely rehashed false receipt.
    """
    modified = replace(original, **modifications)
    root_payload = {
        "problem_root": modified.problem_root,
        "meaning_receipt_root": modified.meaning_receipt_root,
        "verified_relation_receipt_roots": modified.verified_relation_receipt_roots,
        "verified_formal_relation_proof_roots": modified.verified_formal_relation_proof_roots,
        "verified_formal_artifact_roots": modified.verified_formal_artifact_roots,
        "variables": modified.variables,
        "valuation_count": modified.valuation_count,
        "context_truth_union_masks_hex": modified.context_truth_union_masks_hex,
        "global_truth_mask_hex": modified.global_truth_mask_hex,
        "shared_valuation_count": modified.shared_valuation_count,
        "model_kind": modified.model_kind,
        "valuation_index": modified.valuation_index,
        "selected_readings": modified.selected_readings,
    }
    check_root = canonical_hash(DOMAIN_CHECK, root_payload)
    return replace(modified, verification_root=check_root)


@pytest.mark.parametrize("field,value", [
    ("global_truth_mask_hex", "f" * 64),
    ("shared_valuation_count", 12),
    ("valuation_index", 0),
    ("model_kind", SAT),
    ("variables", ("different", "universe")),
    ("verified_formal_relation_proof_roots", ("0" * 64,)),
])
def test_fully_rehashed_semantic_forgeries_denied(triangle, field, value):
    checker, receipts, issued = with_checker(triangle)
    tampered = _reissue_forgery(issued, **{field: value})
    assert tampered.root != issued.root
    receipts.put(tampered)
    assert_denied(
        checker.verify(tampered.root),
        "FINITE_CERTIFICATE_SEMANTIC_CONTENT_MISMATCH",
    )


def test_fully_rehashed_changed_holon_scope_denied(triangle):
    checker, receipts, issued = with_checker(triangle)
    forged = _reissue_forgery(issued, problem_root="f" * 64)
    receipts.put(forged)
    assert_denied(
        checker.verify(forged.root), "FINITE_CERTIFICATE_SCOPE_MISMATCH",
    )


def test_fully_rehashed_wrong_selection_denied():
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    checker, receipts, issued = with_checker(graph)
    incorrect = tuple(
        (ctx, "a-different-reading") for ctx, _ in issued.selected_readings
    )
    tampered = _reissue_forgery(issued, selected_readings=incorrect)
    receipts.put(tampered)
    assert_denied(
        checker.verify(tampered.root),
        "FINITE_CERTIFICATE_SEMANTIC_CONTENT_MISMATCH",
    )


def test_fault_injected_producer_with_consistent_wrong_hash_is_rejected(monkeypatch):
    """A bug in the producer's evaluator cannot convince this checker.

    FiniteFormalRelationVerifierV1 is *not* patched. Its correct pair tables
    still pass. Producer global masks are deliberately corrupted to zero,
    causing an internally hash-consistent but false UNSAT receipt.
    """
    import harness.sdk.holon_finite_global_model as producer
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    genuine_status, genuine = graph["global"].verify(graph["problem"].root)
    assert genuine_status.status == SAT and genuine is not None
    monkeypatch.setattr(producer, "finite_truth_mask", lambda _formula: 0)
    corrupted_status, corrupted = graph["global"].verify(graph["problem"].root)
    assert corrupted_status.status == UNSAT and corrupted is not None
    assert corrupted.root != genuine.root
    receipts = Store()
    receipts.put(corrupted)
    checker = IndependentFiniteCertificateCheckerV1(
        certificates=receipts, indexed=graph["indexed"],
        formal=graph["case"]["verifier"],
    )
    assert_denied(
        checker.verify(corrupted.root),
        "FINITE_CERTIFICATE_SEMANTIC_CONTENT_MISMATCH",
    )
