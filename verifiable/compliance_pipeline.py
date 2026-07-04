#!/usr/bin/env python3
"""
AEGIS-Ω — Regulated decision-audit pipeline (T2 domain proof, second category)
==============================================================================
A DIFFERENT domain on the SAME envelope (verifiable/chain.py) as the genomics
proof. This is AEGIS's stated market: regulated AI middleware, EU AI Act Article 12
record-keeping. A high-stakes automated decision (here: a loan/benefit eligibility
assessment) is only defensible if its record is reproducible and provably un-edited.

Stages: INTAKE -> EXTRACT -> SCORE -> DECISION. Every stage output is folded into the
hash chain. The terminal hash is a tamper-evident decision record: reproducible for
audit, and any post-hoc edit to the inputs, the score, or the decision breaks the
chain and localizes the tampered stage.

Determinism discipline (identical to genomics — that is the point):
  - Integer scoring only. No float weights in hashed state (float is rejected by
    canon()); points are integers, the threshold is an integer.
  - Sorted, list-shaped state — no dict iteration order in the hashed payload.
  - Deterministic reason-code ordering.
  - No wall-clock, no RNG. The applicant record carries its own fields; nothing is
    sampled at runtime.

Honest scope: the scorecard is a toy (four features, fixed points). The claim is the
audit ENVELOPE — reproducibility + tamper-evidence + lineage — not that this is a
validated credit model. T2.
"""
from __future__ import annotations

from chain import LineageChain

# Integer scorecard: (feature, predicate-label) -> points. A real deployment swaps
# this table; the envelope is unchanged. Points are integers so nothing float ever
# enters the hashed decision record.
APPROVE_THRESHOLD = 50  # integer points; >= approves

SCORECARD = {
    "income_band": {"low": 5, "mid": 20, "high": 35},
    "employment": {"none": 0, "part_time": 10, "full_time": 25},
    "prior_defaults": {"yes": -20, "no": 15},
    "residency_years": {"lt2": 0, "2to5": 10, "gt5": 20},
}
# Reason codes attached when a feature contributes non-positively — the "adverse
# action" explanation a regulator requires. Sorted deterministically at emit time.
ADVERSE_CODES = {
    "income_band:low": "AA01_income_below_band",
    "employment:none": "AA02_no_verified_employment",
    "employment:part_time": "AA03_partial_employment",
    "prior_defaults:yes": "AA04_prior_default_on_record",
    "residency_years:lt2": "AA05_insufficient_residency",
}


def intake(applicant: dict) -> dict:
    """Normalize the raw application into the exact fields the scorecard reads.
    Missing fields resolve to the most conservative bucket, deterministically."""
    fields = {
        "income_band": applicant.get("income_band", "low"),
        "employment": applicant.get("employment", "none"),
        "prior_defaults": applicant.get("prior_defaults", "yes"),
        "residency_years": applicant.get("residency_years", "lt2"),
    }
    # applicant_ref is an opaque string id (no PII in the hashed record beyond the ref).
    return {"applicant_ref": str(applicant.get("ref", "UNKNOWN")), "fields": fields}


def extract(intake_out: dict) -> dict:
    """Turn normalized fields into per-feature [feature, value, points] rows,
    sorted by feature name. Unknown values score 0 (deny-by-default)."""
    rows = []
    for feature in sorted(intake_out["fields"]):
        value = intake_out["fields"][feature]
        points = SCORECARD.get(feature, {}).get(value, 0)
        rows.append([feature, value, points])
    return {"features": rows}


def score(extract_out: dict) -> dict:
    """Sum integer points; emit sorted adverse-action reason codes for any feature
    that did not contribute positively. Integer arithmetic only."""
    total = 0
    codes = []
    for feature, value, points in extract_out["features"]:
        total += points
        if points <= 0:
            code = ADVERSE_CODES.get(f"{feature}:{value}")
            if code:
                codes.append(code)
    return {"total_points": total, "adverse_codes": sorted(codes)}


def decide(score_out: dict) -> dict:
    """Integer threshold decision. The decision record binds the outcome, the
    numeric margin, and the adverse-action codes — everything an auditor needs."""
    total = score_out["total_points"]
    approved = total >= APPROVE_THRESHOLD
    return {
        "outcome": "APPROVE" if approved else "DECLINE",
        "total_points": total,
        "threshold": APPROVE_THRESHOLD,
        "margin": total - APPROVE_THRESHOLD,
        "adverse_codes": score_out["adverse_codes"] if not approved else [],
    }


def run_decision(applicant: dict) -> LineageChain:
    """Full governed decision, folded into the verifiable envelope."""
    chain = LineageChain()
    ino = intake(applicant)
    chain.append("INTAKE", ino)
    ext = extract(ino)
    chain.append("EXTRACT", ext)
    sco = score(ext)
    chain.append("SCORE", sco)
    dec = decide(sco)
    chain.append("DECISION", dec)
    return chain


# A fixed, deterministic applicant (an auditor's re-runnable input).
SAMPLE_APPLICANT = {
    "ref": "APP-2026-0007",
    "income_band": "mid",       # 20
    "employment": "full_time",  # 25
    "prior_defaults": "no",     # 15
    "residency_years": "lt2",   # 0  -> AA05
}  # total = 60 >= 50 -> APPROVE


if __name__ == "__main__":
    chain = run_decision(SAMPLE_APPLICANT)
    for rec in chain.records:
        print(f"  {rec.sequence} {rec.stage:10s} {rec.stage_hash[:16]}…")
    dec = chain.records[-1].output
    print(f"decision: {dec['outcome']} ({dec['total_points']} pts, margin {dec['margin']:+d})")
    print("terminal:", chain.terminal_hash())
    print("certify :", chain.certify()["is_valid"])
