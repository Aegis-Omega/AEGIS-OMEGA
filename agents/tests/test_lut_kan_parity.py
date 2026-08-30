"""
Cross-runtime determinism guard for the INT4 LUT-KAN scorer.

The Python port in agents/cognitive_pipeline.py must produce byte-identical
fingerprints and record hashes to the Rust reference in
aegis-cl-psi/src/int4_lut_kan.rs. The Rust side asserts the same reference
vector in its `fingerprint_matches_python_reference` test; this pins the Python
side to it so an edit to the port can't silently break replay determinism
(Tier Promotion Criterion #3 — cross-platform determinism).

These reference hex values are the SAME constants asserted in the Rust test.
If you change the fingerprint/record-hash construction in either language,
both tests must be updated together — that is the point.

Run: python -m agents.tests.test_lut_kan_parity   (or via pytest)
"""

from agents.cognitive_pipeline import (
    fingerprint_inputs,
    _compute_record_hash,
    KAN_GENESIS_HASH,
)

# Byte-identical to aegis-cl-psi/src/int4_lut_kan.rs::fingerprint_matches_python_reference
_REF_FINGERPRINT = "887d1c0263dda885c9bf9848a91bdcd2c7efdb2d3b5a5100feb64de2d8f85549"
_REF_RECORD_HASH = "218edd96c1852207f1c1ed1774f613fa25abf60de6bb3298819b2c4debae6eef"


def test_fingerprint_matches_rust_reference():
    assert fingerprint_inputs([1, 2, 3]).hex() == _REF_FINGERPRINT


def test_record_hash_matches_rust_reference():
    fp = fingerprint_inputs([1, 2, 3])
    rh = _compute_record_hash(KAN_GENESIS_HASH, 0, fp, 42)
    assert rh.hex() == _REF_RECORD_HASH


def test_genesis_is_zero():
    assert KAN_GENESIS_HASH == b"\x00" * 32


if __name__ == "__main__":
    test_fingerprint_matches_rust_reference()
    test_record_hash_matches_rust_reference()
    test_genesis_is_zero()
    print("PASS — Python INT4 LUT-KAN port is byte-identical to the Rust reference.")
