"""Adversarial tests for ResidualVerifierEngineV2 (DERIVED and ATTESTED)."""

from dataclasses import replace
from typing import List, Set

import pytest

from harness.sdk.residual_entailment_v2 import (
    EvidenceClass,
    EvaluatorReturnType,
    IsolationFailureMode,
    QuorumConfig,
    ResidualVerifierEngineV2,
    WitnessVote,
)
from harness.sdk.sovereign_execution import canonical_hash


def mock_atomizer(text: str) -> List[str]:
    return [s.strip() for s in text.split(";") if s.strip()]


def mock_derived_eval(atom: str, ctx: Set[str]) -> EvaluatorReturnType:
    sig = canonical_hash("DERIVED_EVAL_V1", {"atom": atom, "ctx": sorted(ctx)})
    if atom in ctx:
        return True, sig, []
    if atom == "Theorem_Beta" and ("Theorem_Alpha" in ctx and "Alpha_Implies_Beta" in ctx):
        return True, sig, []
    return False, sig, []


def test_derived_lifecycle():
    corpus = {"Theorem_Alpha", "Alpha_Implies_Beta"}
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "v2.0-derived"),
        entailment_evaluator=mock_derived_eval,
        evidence_class=EvidenceClass.DERIVED,
    )

    claim_clean = "Theorem_Gamma; Theorem_Delta"
    receipt_1 = engine.execute_subtraction(claim_clean, corpus)
    valid, errors = engine.verify_residual_entailment(claim_clean, corpus, receipt_1)
    assert valid, errors
    assert len(receipt_1.residual_atom_digests) == 2

    claim_entailed = "Theorem_Beta; Theorem_Gamma"
    receipt_2 = engine.execute_subtraction(claim_entailed, corpus)
    valid, errors = engine.verify_residual_entailment(claim_entailed, corpus, receipt_2)
    assert valid, errors
    assert len(receipt_2.residual_atom_digests) == 1

    corpus_no_alpha = {"Alpha_Implies_Beta"}
    claim_coupled = "Theorem_Alpha; Theorem_Beta"
    receipt_3 = engine.execute_subtraction(claim_coupled, corpus_no_alpha)
    assert receipt_3.isolation_failure_mode == IsolationFailureMode.MUTUAL_DEPENDENCY_DETECTED
    valid_3, errors_3 = engine.verify_residual_entailment(claim_coupled, corpus_no_alpha, receipt_3)
    assert not valid_3
    assert any("ISOLATION_FAULT" in error for error in errors_3)


def _attested_eval(atom: str, ctx: Set[str]) -> EvaluatorReturnType:
    ground_truth = atom in ctx
    votes: List[WitnessVote] = []
    for i in range(3):
        judge_id = f"judge_{i}"
        raw = canonical_hash("RAW", {"judge_id": judge_id, "atom": atom, "ctx": sorted(ctx), "vote": ground_truth})
        sig = canonical_hash(
            "WITNESS_SIG",
            {"judge_id": judge_id, "raw_response_digest": raw, "vote": ground_truth},
        )
        votes.append(WitnessVote(judge_id, ground_truth, raw, sig))
    evaluator_sig = canonical_hash("ATTESTED_EVAL", {"atom": atom, "ctx": sorted(ctx)})
    return ground_truth, evaluator_sig, votes


def test_attested_quorum_consistency():
    corpus = {"Theorem_Alpha"}
    claim = "Theorem_Alpha; Novel_Gamma"
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "v2.0-attested"),
        entailment_evaluator=_attested_eval,
        evidence_class=EvidenceClass.ATTESTED,
        quorum_config=QuorumConfig(required_n=2, total_m=3),
    )

    receipt = engine.execute_subtraction(claim, corpus)
    valid, errors = engine.verify_residual_entailment(claim, corpus, receipt)
    assert valid, errors
    assert len(receipt.residual_atom_digests) == 1


def test_receipt_claim_and_residual_roots_cannot_be_spliced():
    corpus = {"A"}
    claim = "A; B"
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "splice"),
        entailment_evaluator=mock_derived_eval,
        evidence_class=EvidenceClass.DERIVED,
    )
    receipt = engine.execute_subtraction(claim, corpus)

    forged_claim = replace(receipt, claim_digest=canonical_hash("CLAIM", "forged"))
    valid_claim, claim_errors = engine.verify_residual_entailment(claim, corpus, forged_claim)
    assert not valid_claim
    assert "CLAIM_DIGEST_MISMATCH" in claim_errors

    forged_residual = replace(receipt, residual_digest=canonical_hash("RESIDUAL_SET", ["forged"]))
    valid_residual, residual_errors = engine.verify_residual_entailment(claim, corpus, forged_residual)
    assert not valid_residual
    assert "RESIDUAL_DIGEST_MISMATCH" in residual_errors


def test_attested_quorum_requires_distinct_judges_and_exact_total_m():
    corpus: Set[str] = set()
    claim = "Novel"

    def duplicate_judge_eval(atom: str, ctx: Set[str]) -> EvaluatorReturnType:
        vote = False
        raw = canonical_hash("RAW", {"atom": atom, "ctx": sorted(ctx), "vote": vote})
        sig = canonical_hash(
            "WITNESS_SIG",
            {"judge_id": "same", "raw_response_digest": raw, "vote": vote},
        )
        votes = [WitnessVote("same", vote, raw, sig) for _ in range(3)]
        return vote, canonical_hash("ATTESTED_EVAL", atom), votes

    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "quorum-distinct"),
        entailment_evaluator=duplicate_judge_eval,
        evidence_class=EvidenceClass.ATTESTED,
        quorum_config=QuorumConfig(required_n=2, total_m=3),
    )
    receipt = engine.execute_subtraction(claim, corpus)
    valid, errors = engine.verify_residual_entailment(claim, corpus, receipt)
    assert not valid
    assert any("QUORUM_DISTINCT_JUDGES_REQUIRED" in error for error in errors)


def test_engine_binding_and_evidence_class_are_frozen():
    corpus: Set[str] = set()
    claim = "Novel"
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "binding"),
        entailment_evaluator=mock_derived_eval,
        evidence_class=EvidenceClass.DERIVED,
    )
    receipt = engine.execute_subtraction(claim, corpus)

    forged_binding = replace(receipt, verifier_binding=canonical_hash("VERIFIER_CONFIG", "forged"))
    valid_binding, errors_binding = engine.verify_residual_entailment(claim, corpus, forged_binding)
    assert not valid_binding
    assert "VERIFIER_BINDING_MISMATCH" in errors_binding

    forged_class = replace(receipt, evidence_class=EvidenceClass.ATTESTED, quorum_config=QuorumConfig(1, 1))
    valid_class, errors_class = engine.verify_residual_entailment(claim, corpus, forged_class)
    assert not valid_class
    assert "EVIDENCE_CLASS_MISMATCH" in errors_class


def test_retry_chain_requires_sha256_predecessor_and_nonnegative_attempt():
    corpus: Set[str] = set()
    claim = "Novel"
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "retry"),
        entailment_evaluator=mock_derived_eval,
        evidence_class=EvidenceClass.DERIVED,
    )
    receipt = engine.execute_subtraction(claim, corpus)

    negative = replace(receipt, attempt_index=-1)
    valid_negative, negative_errors = engine.verify_residual_entailment(claim, corpus, negative)
    assert not valid_negative
    assert "ATTEMPT_INDEX_INVALID" in negative_errors

    malformed_prev = replace(receipt, attempt_index=1, previous_attempt_sha256="not-a-digest")
    valid_prev, prev_errors = engine.verify_residual_entailment(claim, corpus, malformed_prev)
    assert not valid_prev
    assert "PREVIOUS_ATTEMPT_SHA256_INVALID" in prev_errors


def test_quorum_config_rejects_impossible_thresholds():
    with pytest.raises(ValueError):
        QuorumConfig(required_n=0, total_m=3)
    with pytest.raises(ValueError):
        QuorumConfig(required_n=4, total_m=3)
