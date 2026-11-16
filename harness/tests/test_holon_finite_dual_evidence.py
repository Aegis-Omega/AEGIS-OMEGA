"""End-to-end dual validation, using independently executed Boolean semantics.

The two evidence checks share MHP source custody, formal parsing and hashing.
Tests assert only a finite evidence agreement, not production admission.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from harness.sdk.holon_finite_certificate_checker import (
    IndependentFiniteCertificateCheckerV1,
)
from harness.sdk.holon_finite_dual_evidence import (
    DENIED, PASS, DualFiniteEvidenceVerifierV1,
)
from harness.sdk.holon_finite_global_model import (
    SAT, UNSAT, FiniteGlobalReceiptReplayVerifierV1,
)
from harness.tests.test_holon_finite_global_model import create_graph, triangle
from harness.tests.test_holon_finite_semantics import constant, neg, var
from harness.tests.test_holon_indexed_context import Store


def assemble(graph):
    result, cert = graph["global"].verify(graph["problem"].root)
    assert result.status in (SAT, UNSAT) and cert is not None
    receipts = Store()
    receipts.put(cert)
    replay = FiniteGlobalReceiptReplayVerifierV1(
        receipts=receipts, verifier=graph["global"]
    )
    independent = IndependentFiniteCertificateCheckerV1(
        certificates=receipts, indexed=graph["indexed"],
        formal=graph["case"]["verifier"],
    )
    dual = DualFiniteEvidenceVerifierV1(
        producer_replay=replay, independent=independent,
    )
    return dual, receipts, cert, replay, independent


def denied(output, expected):
    state, receipt = output
    assert state.status == DENIED
    assert state.error_codes == (expected,)
    assert state.verification_root is None and receipt is None


def test_dual_accepts_exact_global_unsat_scope(triangle):
    dual, _, cert, replay, independent = assemble(triangle)
    result, evidence = dual.verify(cert.root)
    assert result.status == PASS and evidence is not None
    assert cert.model_kind == UNSAT
    assert evidence.global_receipt_root == cert.root
    assert evidence.problem_root == cert.problem_root
    assert evidence.meaning_receipt_root == cert.meaning_receipt_root
    assert evidence.global_model_kind == UNSAT
    assert evidence.authority_class == "NONE"
    assert evidence.producer_replay_verification_root == cert.verification_root
    assert evidence.independent_semantic_verification_root == cert.verification_root
    assert result.verification_root == evidence.verification_root
    assert len(evidence.root) == 64
    assert dual.verify(cert.root) == (result, evidence)


def test_dual_accepts_exact_global_sat_witness():
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    dual, _, cert, _, _ = assemble(graph)
    assert cert.model_kind == SAT and cert.valuation_index == 3
    result, evidence = dual.verify(cert.root)
    assert result.status == PASS and evidence is not None
    assert evidence.global_model_kind == SAT
    assert evidence.global_receipt_root == cert.root


def test_dual_accepts_multireading_context_without_normalizing_identity():
    graph = create_graph({
        "left-p": var("p"),
        "left-notp": neg(var("p")),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    dual, _, cert, _, _ = assemble(graph)
    assert cert.shared_valuation_count == 2
    check, receipt = dual.verify(cert.root)
    assert check.status == PASS and receipt is not None
    assert receipt.global_receipt_root == cert.root


def test_dual_accepts_complete_256_valuation_boundary():
    graph = create_graph({
        "left-a": var("a"),
        "left-nota": neg(var("a")),
        "right-true": constant(True),
        "third-true": constant(True),
    }, variables=tuple("abcdefgh"))
    dual, _, cert, _, _ = assemble(graph)
    assert cert.valuation_count == 256
    check, receipt = dual.verify(cert.root)
    assert check.status == PASS and receipt is not None
    assert receipt.global_model_kind == SAT


@pytest.mark.parametrize("bad", ("", "not-a-hash", "Z" * 64))
def test_dual_rejects_unparseable_receipt_roots(bad, triangle):
    dual, _, _, _, _ = assemble(triangle)
    denied(dual.verify(bad), "DUAL_RECEIPT_ROOT_INVALID")


def test_dual_refuses_missing_custody_receipt(triangle):
    dual, receipts, cert, _, _ = assemble(triangle)
    receipts.items.clear()
    denied(dual.verify(cert.root), "DUAL_PRODUCER_REPLAY_DENIED")


def test_dual_refuses_stale_original_lineage(triangle):
    dual, _, cert, _, _ = assemble(triangle)
    triangle["case"]["verifier"].meaning_verifier.heritage.data.clear()
    denied(dual.verify(cert.root), "DUAL_PRODUCER_REPLAY_DENIED")


def test_dual_refuses_missing_pair_table_record(triangle):
    dual, _, cert, _, _ = assemble(triangle)
    del triangle["case"]["relations"].data[triangle["links"][1].root]
    denied(dual.verify(cert.root), "DUAL_PRODUCER_REPLAY_DENIED")


def test_dual_refuses_changed_receipt_with_old_content_address(triangle):
    dual, receipts, cert, _, _ = assemble(triangle)
    receipts.items[cert.root] = replace(
        cert, shared_valuation_count=100
    )
    denied(dual.verify(cert.root), "DUAL_PRODUCER_REPLAY_DENIED")


def test_dual_catches_corrupt_producer_even_when_its_replay_agrees(monkeypatch):
    # The main producer and its replay deliberately share the same error.
    # An unsound 'two checks of the same code' arrangement would accept.
    import harness.sdk.holon_finite_global_model as producer
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    check, original = graph["global"].verify(graph["problem"].root)
    assert check.status == SAT and original is not None
    monkeypatch.setattr(producer, "finite_truth_mask", lambda formula: 0)
    dual, receipts, corrupt, replay, independent = assemble(graph)
    assert corrupt.model_kind == UNSAT
    assert corrupt.root != original.root
    check_replay, cert_replay = replay.verify(corrupt.root)
    assert check_replay.status == UNSAT and cert_replay == corrupt
    check_independent, result_independent = independent.verify(corrupt.root)
    assert check_independent.status != "PASS_INDEPENDENT_FINITE_BOOLEAN_CERTIFICATE_ONLY"
    assert result_independent is None
    denied(dual.verify(corrupt.root), "DUAL_INDEPENDENT_SEMANTICS_DENIED")


def test_dual_catches_fault_injected_independent_evaluator(monkeypatch):
    import harness.sdk.holon_finite_certificate_checker as checker_module
    graph = create_graph({
        "left-p": var("p"),
        "right-q": var("q"),
        "third-true": constant(True),
    })
    dual, _, cert, replay, independent = assemble(graph)
    monkeypatch.setattr(checker_module, "_eval_independent", lambda tree, assignment: False)
    first, recomputed = replay.verify(cert.root)
    assert first.status == SAT and recomputed == cert
    denied(dual.verify(cert.root), "DUAL_INDEPENDENT_SEMANTICS_DENIED")


def test_dual_does_not_confer_authority_on_pass(triangle):
    dual, _, cert, _, _ = assemble(triangle)
    check, evidence = dual.verify(cert.root)
    assert check.status == PASS and evidence is not None
    assert evidence.authority_class == "NONE"
    assert check.status != SAT and check.status != UNSAT
