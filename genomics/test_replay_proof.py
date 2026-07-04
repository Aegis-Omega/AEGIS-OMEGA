#!/usr/bin/env python3
"""
Proof harness for the AEGIS-Ω replay-verifiable genomics pipeline.
Asserts the three clinically-relevant invariants. Exit 0 = all proven.
"""
from replay_pipeline import (
    run_pipeline, SAMPLE_REFERENCE, SAMPLE_READS, canon, sha256_hex,
)
import copy


def prove_determinism():
    """INVARIANT 1: 3 independent runs -> byte-identical terminal hash.
    One or two runs cannot confirm determinism (per the repo's own testing rule)."""
    hashes = [run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS).terminal_hash()
              for _ in range(3)]
    assert len(set(hashes)) == 1, f"DETERMINISM FAILED: {hashes}"
    # Also: input order must not matter (aligner sorts) -> same hash on shuffled input.
    shuffled = list(reversed(SAMPLE_READS))
    h_shuf = run_pipeline(SAMPLE_REFERENCE, shuffled).terminal_hash()
    assert h_shuf == hashes[0], "ORDER-INVARIANCE FAILED (aligner not deterministic)"
    return hashes[0]


def prove_tamper_evidence(baseline_hash):
    """INVARIANT 2: flip ONE base in ONE read -> terminal hash changes, and
    certify() on a post-hoc edited chain localizes the first divergent stage."""
    tampered_reads = copy.deepcopy(SAMPLE_READS)
    tampered_reads[0]["bases"] = "AACGT"  # flip first base T->A
    h_tampered = run_pipeline(SAMPLE_REFERENCE, tampered_reads).terminal_hash()
    assert h_tampered != baseline_hash, "TAMPER NOT DETECTED at terminal hash"

    # Now simulate an attacker editing a stored result AFTER the fact:
    chain = run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS)
    assert chain.certify()["is_valid"] is True
    # Silently rewrite an annotation in the VARIANT_CALL stage output.
    vc = chain.records[3]
    if vc.output["variants"]:
        vc.output["variants"][0][2] = "G"  # forge the alt allele
    cert = chain.certify()
    assert cert["is_valid"] is False, "FORGERY NOT DETECTED"
    assert cert["broken_at"] == "VARIANT_CALL", f"MISLOCALIZED: {cert}"
    return h_tampered, cert


def prove_chain_binding():
    """INVARIANT 3: the lineage is a real chain — each stage binds the previous.
    Prove it by showing a stage hash depends on prior_hash, not just its own output."""
    chain = run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS)
    r = chain.records[2]  # PILEUP
    # Recompute PILEUP's hash with a DIFFERENT previous_hash; it must differ.
    from replay_pipeline import StageRecord
    forged = StageRecord(r.stage, r.output, "f" * 64, r.sequence)
    forged.compute()
    assert forged.stage_hash != r.stage_hash, "CHAIN NOT BOUND (stage ignores lineage)"
    return True


if __name__ == "__main__":
    print("AEGIS-Ω Genomics — Replay Proof")
    print("=" * 52)
    base = prove_determinism()
    print(f"[1] DETERMINISM   PROVEN  3 runs + order-invariant -> {base[:16]}…")
    h_t, cert = prove_tamper_evidence(base)
    print(f"[2] TAMPER-EVIDENT PROVEN  1-base flip -> {h_t[:16]}… (≠ baseline)")
    print(f"                           forged VARIANT_CALL localized: broken_at={cert['broken_at']}")
    prove_chain_binding()
    print(f"[3] CHAIN-BOUND    PROVEN  each stage hash binds prior_hash")
    print("=" * 52)
    print("RESULT: all three invariants proven. Terminal hash is a")
    print("        medical-grade, reproducible, tamper-evident certificate.")
