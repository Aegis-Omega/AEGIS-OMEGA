#!/usr/bin/env python3
"""
Evidence–Claim Divergence reference estimator (T2 research instrument).

This module gives the ECD / Hallucination Distance paper a small, deterministic,
stdlib-only reference implementation over observable claims and evidence nodes. It
is intentionally conservative: it measures claim/evidence alignment, not truth,
intent, or model quality.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from chain import LineageChain


@dataclass(frozen=True)
class Claim:
    claim_id: str
    subject: str
    predicate: str
    value: str
    confidence_ppm: int = 1_000_000
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceNode:
    evidence_id: str
    subject: str
    predicate: str
    value: str
    verified: bool = True


@dataclass(frozen=True)
class HDWeights:
    execution: int = 1
    omission: int = 1
    unsupported: int = 1
    contradiction: int = 1
    calibration: int = 1


@dataclass(frozen=True)
class HDResult:
    execution_divergence: Fraction
    evidence_omission: Fraction
    unsupported_assertions: Fraction
    contradictory_claims: Fraction
    calibration_mismatch: Fraction
    hallucination_distance: Fraction
    evidence_quality: Fraction
    verified_evidence: int
    total_evidence: int

    def as_payload(self) -> dict:
        return {
            "execution_divergence_ppm": ppm(self.execution_divergence),
            "evidence_omission_ppm": ppm(self.evidence_omission),
            "unsupported_assertions_ppm": ppm(self.unsupported_assertions),
            "contradictory_claims_ppm": ppm(self.contradictory_claims),
            "calibration_mismatch_ppm": ppm(self.calibration_mismatch),
            "hallucination_distance_ppm": ppm(self.hallucination_distance),
            "evidence_quality_ppm": ppm(self.evidence_quality),
            "verified_evidence": self.verified_evidence,
            "total_evidence": self.total_evidence,
        }


def ppm(x: Fraction) -> int:
    return int(x * 1_000_000)


def _claim_key(claim: Claim) -> tuple[str, str]:
    return claim.subject, claim.predicate


def _evidence_key(node: EvidenceNode) -> tuple[str, str]:
    return node.subject, node.predicate


def estimate_hd(
    claims: Iterable[Claim],
    evidence: Iterable[EvidenceNode],
    weights: HDWeights = HDWeights(),
) -> HDResult:
    claim_list = sorted(claims, key=lambda c: c.claim_id)
    evidence_list = sorted(evidence, key=lambda e: e.evidence_id)
    total_claims = len(claim_list)
    total_evidence = len(evidence_list)
    verified_evidence = sum(1 for node in evidence_list if node.verified)

    if total_claims == 0:
        zero = Fraction(0, 1)
        quality = Fraction(verified_evidence, total_evidence) if total_evidence else zero
        return HDResult(zero, zero, zero, zero, zero, zero, quality, verified_evidence, total_evidence)

    evidence_by_id = {node.evidence_id: node for node in evidence_list}
    verified_by_key: dict[tuple[str, str], list[EvidenceNode]] = {}
    for node in evidence_list:
        if node.verified:
            verified_by_key.setdefault(_evidence_key(node), []).append(node)

    execution_mismatches = 0
    omissions = 0
    unsupported = 0
    calibration_error = Fraction(0, 1)
    seen_values: dict[tuple[str, str], set[str]] = {}

    for claim in claim_list:
        key = _claim_key(claim)
        supporting = [evidence_by_id[eid] for eid in claim.evidence_ids if eid in evidence_by_id and evidence_by_id[eid].verified]
        candidates = supporting or verified_by_key.get(key, [])
        matching = [node for node in candidates if _evidence_key(node) == key and node.value == claim.value]

        if not claim.evidence_ids:
            omissions += 1
        elif not supporting:
            unsupported += 1
        if not matching:
            execution_mismatches += 1

        observed_correct = Fraction(1, 1) if matching else Fraction(0, 1)
        expressed = Fraction(claim.confidence_ppm, 1_000_000)
        calibration_error += abs(expressed - observed_correct)
        seen_values.setdefault(key, set()).add(claim.value)

    contradictory_groups = sum(1 for values in seen_values.values() if len(values) > 1)
    possible_groups = len(seen_values) or 1

    execution = Fraction(execution_mismatches, total_claims)
    omission = Fraction(omissions, total_claims)
    unsupported_rate = Fraction(unsupported, total_claims)
    contradiction = Fraction(contradictory_groups, possible_groups)
    calibration = calibration_error / total_claims
    quality = Fraction(verified_evidence, total_evidence) if total_evidence else Fraction(0, 1)

    weight_total = weights.execution + weights.omission + weights.unsupported + weights.contradiction + weights.calibration
    hd = (
        weights.execution * execution
        + weights.omission * omission
        + weights.unsupported * unsupported_rate
        + weights.contradiction * contradiction
        + weights.calibration * calibration
    ) / weight_total

    return HDResult(execution, omission, unsupported_rate, contradiction, calibration, hd, quality, verified_evidence, total_evidence)


def hd_delta(previous: HDResult, current: HDResult, elapsed_ticks: int) -> Fraction:
    if elapsed_ticks <= 0:
        raise ValueError("elapsed_ticks must be positive")
    return (current.hallucination_distance - previous.hallucination_distance) / elapsed_ticks


def measurement_chain(result: HDResult) -> LineageChain:
    chain = LineageChain()
    chain.append("ECD_ESTIMATE", result.as_payload())
    return chain
