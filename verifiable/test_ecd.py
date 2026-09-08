#!/usr/bin/env python3
"""Deterministic checks for the Evidence–Claim Divergence estimator."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ecd import Claim, EvidenceNode, estimate_hd, hd_delta, measurement_chain, ppm


def test_perfect_alignment_has_zero_hd_and_full_quality():
    evidence = [EvidenceNode("e1", "run", "exit_code", "0")]
    claims = [Claim("c1", "run", "exit_code", "0", evidence_ids=("e1",))]
    result = estimate_hd(claims, evidence)
    assert result.hallucination_distance == 0
    assert result.evidence_quality == 1


def test_unsupported_and_contradictory_claims_increase_hd():
    evidence = [EvidenceNode("e1", "run", "exit_code", "0")]
    clean = estimate_hd([Claim("c1", "run", "exit_code", "0", evidence_ids=("e1",))], evidence)
    corrupted = estimate_hd([
        Claim("c1", "run", "exit_code", "0", evidence_ids=("e1",)),
        Claim("c2", "run", "exit_code", "1", confidence_ppm=900_000, evidence_ids=("missing",)),
    ], evidence)
    assert corrupted.hallucination_distance > clean.hallucination_distance
    assert corrupted.unsupported_assertions > 0
    assert corrupted.contradictory_claims > 0


def test_measurement_chain_is_reproducible_and_tamper_evident():
    result = estimate_hd([Claim("c1", "run", "exit_code", "0", evidence_ids=("e1",))], [EvidenceNode("e1", "run", "exit_code", "0")])
    chain_a = measurement_chain(result)
    chain_b = measurement_chain(result)
    assert chain_a.terminal_hash() == chain_b.terminal_hash()
    chain_a.records[0].output["hallucination_distance_ppm"] = 1
    assert chain_a.certify()["is_valid"] is False


def test_hd_delta_uses_deterministic_ticks():
    evidence = [EvidenceNode("e1", "run", "exit_code", "0")]
    before = estimate_hd([Claim("c1", "run", "exit_code", "0", evidence_ids=("e1",))], evidence)
    after = estimate_hd([Claim("c1", "run", "exit_code", "1", confidence_ppm=1_000_000, evidence_ids=("e1",))], evidence)
    assert ppm(hd_delta(before, after, elapsed_ticks=2)) > 0


if __name__ == "__main__":
    tests = [
        test_perfect_alignment_has_zero_hd_and_full_quality,
        test_unsupported_and_contradictory_claims_increase_hd,
        test_measurement_chain_is_reproducible_and_tamper_evident,
        test_hd_delta_uses_deterministic_ticks,
    ]
    for test in tests:
        test()
    print(f"ECD estimator checks passed: {len(tests)}")
