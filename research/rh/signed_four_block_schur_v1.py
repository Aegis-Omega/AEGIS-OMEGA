"""Exact Schur/inertia preformalization certificate for RH_SIGNED_FOUR_BLOCK_V1.

This script works with the ACTUAL four-by-four compression

    M[i,j] = B(T_{i log 2} gFine, T_{j log 2} gFine),  i,j = 0,1,2,3.

RHSignedFourBlockRealityV1 reduces M to a real-symmetric Toeplitz matrix.
Write E = energy(gFine), d = -M[0,0]/E and
r_k = M[0,k]/E for k=1,2,3 (when E>0).

Existing source theorems give

    d >= 32/25,
    |r1| <= 51/100,
    |r2| <= 9/25,
    |r3| <= 13/50.

The reversal-even and reversal-odd blocks of A = -M/E are

    A_even = [[d-r3, -(r1+r2)],
              [-(r1+r2), d-r1]]

    A_odd  = [[d+r3, -(r1-r2)],
              [-(r1-r2), d+r1]].

This certificate proves, using exact rational arithmetic only, that both
blocks remain positive definite after subtracting lambda = 2/125 from the
diagonal. Hence every eigenvalue of A is > 2/125 and the actual B-compression
is strictly negative definite (for E>0), with the same coercivity margin as
the existing four-packet theorem.

The arithmetic certificate is not a substitute for Lean replay of the source
theorems. It is the hard preformalization gate requested before formalizing
Schur/inertia.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction as F
import json

DIAGONAL_LOWER = F(32, 25)
B1_ABS_UPPER = F(51, 100)
B2_ABS_UPPER = F(9, 25)
B3_ABS_UPPER = F(13, 50)
COERCIVITY = F(2, 125)

# Signed lower enclosures already derived by signed_four_block_preflight_v1.py.
B1_LOWER = F(4751, 10000)
B2_LOWER = F(673, 2000)
B3_LOWER = F(4651, 20000)


@dataclass(frozen=True)
class SignedFourBlockSchurCertificateV1:
    diagonal_lower: F
    b1_interval_lower: F
    b1_abs_upper: F
    b2_interval_lower: F
    b2_abs_upper: F
    b3_interval_lower: F
    b3_abs_upper: F
    coercivity: F
    shifted_diagonal: F
    block_diag_far_lower: F
    block_diag_adj_lower: F
    block_offdiag_abs_upper: F
    unshifted_schur_det_lower: F
    shifted_schur_det_lower: F
    schur_gate_pass: bool
    normalized_inertia: tuple[int, int, int]

    def to_dict(self) -> dict[str, object]:
        def enc(v):
            if isinstance(v, F):
                return {"numerator": v.numerator, "denominator": v.denominator}
            if isinstance(v, tuple):
                return list(v)
            return v
        return {k: enc(v) for k, v in asdict(self).items()}


def compute_certificate() -> SignedFourBlockSchurCertificateV1:
    shifted = DIAGONAL_LOWER - COERCIVITY

    # Both reversal blocks have the same conservative lower certificate:
    # diagonal entries >= shifted-|r3| and shifted-|r1|;
    # |offdiag| <= |r1|+|r2|.
    diag_far = shifted - B3_ABS_UPPER
    diag_adj = shifted - B1_ABS_UPPER
    off = B1_ABS_UPPER + B2_ABS_UPPER

    unshifted_det = (
        (DIAGONAL_LOWER - B3_ABS_UPPER)
        * (DIAGONAL_LOWER - B1_ABS_UPPER)
        - off * off
    )
    shifted_det = diag_far * diag_adj - off * off

    gate = diag_far > 0 and diag_adj > 0 and shifted_det > 0
    return SignedFourBlockSchurCertificateV1(
        diagonal_lower=DIAGONAL_LOWER,
        b1_interval_lower=B1_LOWER,
        b1_abs_upper=B1_ABS_UPPER,
        b2_interval_lower=B2_LOWER,
        b2_abs_upper=B2_ABS_UPPER,
        b3_interval_lower=B3_LOWER,
        b3_abs_upper=B3_ABS_UPPER,
        coercivity=COERCIVITY,
        shifted_diagonal=shifted,
        block_diag_far_lower=diag_far,
        block_diag_adj_lower=diag_adj,
        block_offdiag_abs_upper=off,
        unshifted_schur_det_lower=unshifted_det,
        shifted_schur_det_lower=shifted_det,
        schur_gate_pass=gate,
        # inertia of A=-M/E in (positive, negative, zero) convention.
        normalized_inertia=(4, 0, 0) if gate else (0, 0, 0),
    )


def main() -> None:
    cert = compute_certificate()
    assert cert.shifted_diagonal == F(158, 125)
    assert cert.block_diag_far_lower == F(251, 250)
    assert cert.block_diag_adj_lower == F(377, 500)
    assert cert.block_offdiag_abs_upper == F(87, 100)
    assert cert.unshifted_schur_det_lower == F(57, 2000)
    assert cert.shifted_schur_det_lower == F(29, 250000)
    assert cert.schur_gate_pass
    print(json.dumps(cert.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
