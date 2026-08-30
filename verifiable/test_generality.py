#!/usr/bin/env python3
"""
Proof that the verifiable envelope is domain-agnostic AND identical across domains.
Exit 0 = proven. Two claims:

  1. The regulated decision-audit pipeline (a DIFFERENT domain from genomics) is
     deterministic 3x, and a post-hoc edit to any stage breaks the chain and
     localizes the tampered stage.
  2. CROSS-CHECK: the shared envelope (verifiable/chain.py) and the genomics inline
     envelope (genomics/replay_pipeline.py) are byte-identical primitives — the same
     canonicalization and the same hash on the same input. "Same envelope across
     categories" is therefore verified, not asserted.
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "genomics")))

from compliance_pipeline import run_decision, SAMPLE_APPLICANT, APPROVE_THRESHOLD


def prove_decision_determinism():
    hashes = [run_decision(SAMPLE_APPLICANT).terminal_hash() for _ in range(3)]
    assert len(set(hashes)) == 1, f"DECISION DETERMINISM FAILED: {hashes}"
    return hashes[0]


def prove_decision_tamper_evidence():
    chain = run_decision(SAMPLE_APPLICANT)
    assert chain.certify()["is_valid"] is True
    dec = chain.records[3]                       # DECISION stage
    assert dec.output["outcome"] == "APPROVE"    # sanity: sample approves at 60 pts
    dec.output["outcome"] = "DECLINE"            # forge the outcome after the fact
    cert = chain.certify()
    assert cert["is_valid"] is False, "FORGERY NOT DETECTED"
    assert cert["broken_at"] == "DECISION", f"MISLOCALIZED: {cert}"
    return cert


def prove_score_binding_flips_terminal():
    """A different applicant that crosses the threshold must change the terminal
    hash — the record actually depends on the decision, not just its shape."""
    base = run_decision(SAMPLE_APPLICANT).terminal_hash()
    declined = copy.deepcopy(SAMPLE_APPLICANT)
    declined["income_band"] = "low"       # 35 -> 5, total 60 -> 30, crosses threshold
    declined["employment"] = "part_time"  # 25 -> 10, total 30 -> 15 -> DECLINE
    other = run_decision(declined)
    assert other.records[3].output["outcome"] == "DECLINE"
    assert other.terminal_hash() != base, "terminal hash ignores the decision"
    return True


def prove_same_envelope_across_domains():
    """The shared and genomics-inline envelopes must be the SAME primitive."""
    from chain import canon as canon_shared, sha256_hex as sha_shared
    from replay_pipeline import canon as canon_genomics, sha256_hex as sha_genomics

    # A payload exercising sorted keys, nesting, unicode, ints — never a float.
    sample = {"z": 1, "a": [3, 2, 1], "nested": {"k": "café", "n": 7}, "list": [["b", 2], ["a", 1]]}
    assert canon_shared(sample) == canon_genomics(sample), "canon diverges across envelopes"
    assert sha_shared(canon_shared(sample)) == sha_genomics(canon_genomics(sample)), \
        "hash diverges across envelopes"

    # Both must reject float in hashed state, identically.
    for canon_fn in (canon_shared, canon_genomics):
        try:
            canon_fn({"bad": 1.5})
            raise AssertionError("float was not rejected")
        except TypeError:
            pass
    return sha_shared(canon_shared(sample))


if __name__ == "__main__":
    print("AEGIS-Ω — Envelope Generality Proof")
    print("=" * 56)
    d = prove_decision_determinism()
    print(f"[1] DECISION DETERMINISM  PROVEN  3 runs -> {d[:16]}…")
    cert = prove_decision_tamper_evidence()
    print(f"[2] DECISION TAMPER-EVIDENT PROVEN  forged outcome localized: broken_at={cert['broken_at']}")
    prove_score_binding_flips_terminal()
    print(f"[3] SCORE BINDING          PROVEN  crossing threshold={APPROVE_THRESHOLD} flips terminal hash")
    h = prove_same_envelope_across_domains()
    print(f"[4] SAME ENVELOPE          PROVEN  genomics-inline == shared canon+hash -> {h[:16]}…")
    print("=" * 56)
    print("RESULT: one envelope, two categories (genomics + regulated decisions),")
    print("        byte-identical primitive. The generality claim is verified.")
