"""Adversarial tests for the evidence-only P_SHP lock controller."""

from dataclasses import replace
from typing import List, Set

from harness.sdk.pshp_lock import PSHPLockController
from harness.sdk.residual_entailment_v2 import (
    EvidenceClass,
    EvaluatorReturnType,
    QuorumConfig,
    ResidualVerifierEngineV2,
    WitnessVote,
)
from harness.sdk.sovereign_execution import canonical_hash


def mock_atomizer(text: str) -> List[str]:
    return [s.strip() for s in text.split(";") if s.strip()]


def mock_eval(atom: str, ctx: Set[str]) -> EvaluatorReturnType:
    signature = canonical_hash("DERIVED_EVAL_V1", {"atom": atom, "ctx": sorted(ctx)})
    return (atom in ctx), signature, []


def _attested_eval(atom: str, ctx: Set[str]) -> EvaluatorReturnType:
    outcome = atom in ctx
    votes = []
    for i in range(3):
        judge_id = f"j{i}"
        raw = canonical_hash("RAW", {"judge_id": judge_id, "atom": atom, "ctx": sorted(ctx), "vote": outcome})
        sig = canonical_hash(
            "WITNESS_SIG",
            {"judge_id": judge_id, "raw_response_digest": raw, "vote": outcome},
        )
        votes.append(WitnessVote(judge_id, outcome, raw, sig))
    return outcome, canonical_hash("ATTESTED_EVAL", {"atom": atom, "ctx": sorted(ctx)}), votes


def test_pshp_lock_full_state_matrix():
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "v1"),
        entailment_evaluator=mock_eval,
        evidence_class=EvidenceClass.DERIVED,
    )
    controller = PSHPLockController(engine)

    corpus_0 = {"Axiom_1"}
    claim = "Axiom_1; Lemma_2"
    atom_map = {canonical_hash("ATOM", atom): atom for atom in mock_atomizer(claim)}

    receipt = engine.execute_subtraction(claim, corpus_0)
    ok, record, corpus_1, errors = controller.attempt_lock(claim, corpus_0, receipt, atom_map)
    assert ok, errors
    assert corpus_1 == {"Axiom_1", "Lemma_2"}
    assert corpus_0 == {"Axiom_1"}
    assert record is not None
    assert record.authority_class == "NONE"

    ok_missing, record_missing, corpus_missing, errors_missing = controller.attempt_lock(
        claim, corpus_0, receipt, {}
    )
    assert not ok_missing
    assert record_missing is None
    assert corpus_missing == corpus_0
    assert any("MISSING_ATOM_CONTENT" in error for error in errors_missing)

    engine_attested = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "v1-att"),
        entailment_evaluator=_attested_eval,
        evidence_class=EvidenceClass.ATTESTED,
        quorum_config=QuorumConfig(required_n=2, total_m=3),
    )
    controller_attested = PSHPLockController(engine_attested)
    attested_receipt = engine_attested.execute_subtraction(claim, corpus_0)

    ok_denied, denied_record, denied_corpus, denied_errors = controller_attested.attempt_lock(
        claim,
        corpus_0,
        attested_receipt,
        atom_map,
        manual_ack=False,
    )
    assert not ok_denied
    assert denied_record is None
    assert denied_corpus == corpus_0
    assert "ATTESTED_MANUAL_ACK_REQUIRED" in denied_errors

    ok_ack, ack_record, ack_corpus, ack_errors = controller_attested.attempt_lock(
        claim,
        corpus_0,
        attested_receipt,
        atom_map,
        manual_ack=True,
    )
    assert ok_ack, ack_errors
    assert ack_record is not None
    assert ack_record.authority_class == "NONE"
    assert ack_corpus == {"Axiom_1", "Lemma_2"}


def test_atom_map_content_is_digest_bound_and_cannot_be_spliced():
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "atom-map-binding"),
        entailment_evaluator=mock_eval,
        evidence_class=EvidenceClass.DERIVED,
    )
    controller = PSHPLockController(engine)
    corpus = {"A"}
    claim = "A; B"
    receipt = engine.execute_subtraction(claim, corpus)
    residual_digest = receipt.residual_atom_digests[0]

    forged_atom_map = {residual_digest: "MALICIOUS_DIFFERENT_ATOM"}
    ok, record, successor, errors = controller.attempt_lock(claim, corpus, receipt, forged_atom_map)
    assert not ok
    assert record is None
    assert successor == corpus
    assert "ATOM_CONTENT_DIGEST_MISMATCH" in errors


def test_lock_denies_tampered_receipt_without_state_change():
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "tamper"),
        entailment_evaluator=mock_eval,
        evidence_class=EvidenceClass.DERIVED,
    )
    controller = PSHPLockController(engine)
    corpus = {"A"}
    claim = "A; B"
    atom_map = {canonical_hash("ATOM", atom): atom for atom in mock_atomizer(claim)}
    receipt = engine.execute_subtraction(claim, corpus)
    forged = replace(receipt, corpus_snapshot_digest=canonical_hash("CORPUS", ["OTHER"]))

    ok, record, successor, errors = controller.attempt_lock(claim, corpus, forged, atom_map)
    assert not ok
    assert record is None
    assert successor == corpus
    assert errors


def test_lock_record_is_deterministic_evidence_not_authority():
    engine = ResidualVerifierEngineV2(
        atomizer=mock_atomizer,
        atomizer_contract_digest=canonical_hash("CONTRACT", "determinism"),
        entailment_evaluator=mock_eval,
        evidence_class=EvidenceClass.DERIVED,
    )
    controller = PSHPLockController(engine)
    corpus = {"A"}
    claim = "A; B"
    atom_map = {canonical_hash("ATOM", atom): atom for atom in mock_atomizer(claim)}
    receipt = engine.execute_subtraction(claim, corpus)

    ok1, record1, successor1, errors1 = controller.attempt_lock(claim, corpus, receipt, atom_map)
    ok2, record2, successor2, errors2 = controller.attempt_lock(claim, corpus, receipt, atom_map)
    assert ok1 and ok2 and not errors1 and not errors2
    assert record1 is not None and record2 is not None
    assert record1.compute_lock_hash() == record2.compute_lock_hash()
    assert record1.authority_class == record2.authority_class == "NONE"
    assert successor1 == successor2
