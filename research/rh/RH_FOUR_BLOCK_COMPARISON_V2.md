# Four-block comparison V2: scope repair and narrower diagonal

## Source binding and evidence boundary

Base integration PR: #580, `cfe368ce2ffa0d196a4319c02b956997edf9f3fa`.
Parent of this change: `d3a4d26c27339e2be538846fb401b36c58c5cf96` on
`proof/rh-four-block-margin-v1`. The integration branch is not modified.

This package contains an exact rational comparison certificate, candidate
Lean proofs, and a written analytic derivation. These are different evidence
levels. Python tests do not constitute Lean kernel replay, and matrix
positivity does not automatically establish positivity of the actual Weil
form. `authority_effect = NONE`. No merge, deployment, workflow dispatch,
rerun, governance-anchor modification, or RH promotion is performed.

The local runtime has no Lean/Lake installation. An attempt to reach the
pinned Lean release failed at DNS resolution; a separate download attempt
also failed. No Lean compiler process ran. Accordingly, Lean kernel and
axiom audit remain `NOT_RUN`, not `PASS` or `PROOF_FAIL`.

## 1. Correction of the 9/8 inference

Let a=51/100 and b=9/25. Omitting the farthest pair gives

    Q_d(x) = d sum_i x_i^2
             - 2a(x0 x1 + x1 x2 + x2 x3)
             - 2b(x0 x2 + x1 x3).

The old equation says Q_(9/8)(1,1,1,1)=0. It says nothing about all vectors.
Indeed Q_(9/8)(4,5,5,4)=-57/20. The prior Lean arithmetic statements are kept
unchanged, while their comments are corrected. This is a counterexample to
an interpretation of the scalar budget, NOT a counterexample to RH or to
the existing actual three-block theorem.

## 2. Complete six-pair comparison certificate

Retain the farthest coefficient r explicitly. Let

    C = [[0,a,b,r], [a,0,a,b], [b,a,0,a], [r,b,a,0]].

For d,a,b,r and arbitrary real x, set u=x0+x3, v=x1+x2,
s=x0-x3 and t=x1-x2. Direct expansion gives

    2(d ||x||^2 - x^T C x)
      = (d-r)u^2 + (d-a)v^2 - 2(a+b)uv
        + (d+r)s^2 + (d+a)t^2 - 2(a-b)st.

This also records where signed structure survives; it does not assume sign.

For a=51/100, b=9/25 and r=13/50, the following polynomial identity is exact:

    (158/125) sum_i x_i^2 - x^T C x
    = (17/6500)[(15x0-13x1)^2 + (13x2-15x3)^2]
      + (3/1625)[(15x0-13x2)^2 + (13x1-15x3)^2]
      + (51/100)(x1-x2)^2 + (13/50)(x0-x3)^2
      + (1/6500)(x0^2+x3^2).

Every coefficient on the right is positive. Thus x^T C x <= (158/125)||x||^2
for EVERY real vector, not just sampled vectors. The weights (13,15,15,13)
give row quotients (1643/1300,158/125,158/125,1643/1300); the endpoint
residuals are exactly 1/6500. No claim of an optimal threshold is made.

The independent standard-library Python verifier checks equality of all 16
matrix coefficients with exact fractions. Its negative controls reject a
lower diagonal, a larger farthest entry, a silently deleted pair, negative
SOS coefficients, and altered positive coefficients. It also runs under
Python optimization; validation does not rely on removable assertions.

## 3. A real analytic diagonal improvement on a narrower class

This section uses the definitions and identities in the existing V2.6/V2.7
and V3.1 source chain. Their imported exact-head Lean replay is not asserted.

Let E=energy(g), A=Autocorrelation(g), and suppose the logarithmic support of
g has TOTAL width <=1/64 (half-width 1/128). This is stricter than the existing
width-1/32 class. It is not inferred from the original gNarrow seed radius.

The inherited transformed Archimedean integrand is

    F(u) = [exp(u) Re A(exp u) - E] / sinh(u).

Support differences imply A(exp u)=0 for u>1/64. In particular, on
J=(1/64,1/32], F(u)=-E/sinh(u). Also

    exp(u) <= 16/15,
    exp(-u) >= 1-u >= 31/32,
    sinh(u) <= (16/15 - 31/32)/2 = 47/960 < 1/16.

Consequently F(u)<=-16E on J. The interval has length 1/64, so

    integral_J F <= -E/4.

On (0,1/64], retain the old upper bound E exp(1/64)/2. Its integral is at
most half the old V2.7 small-window budget. Keeping the weaker full old
budget is therefore safe. The tail beyond 1/32 is unchanged. Together,

    Re Arch(A) <= E*(diagonalSmallV21-diagonalTailV24) - E/4.

Using the same prime-sum vanishing and scalar floor as the old V2.7 proof
then yields

    -Re B(g,g) >= (103/100 + 1/4)E = (32/25)E.

No moment premise is needed for this diagonal-only improvement. The source
candidate `RHNarrowDiagonalUpgradeV2.lean` formalizes the narrower support,
the vanishing, the middle-window estimate, the integral split, and this
final diagonal bound. Its compilation and axiom audit remain unperformed.

## 4. Conditional binding to the ACTUAL arithmetic B

`RHFourBlockActualBridgeV2.lean` defines four packets using the existing
`addPacket`, `scalePacket` and `combo`, and expands the same repository `B`
using its existing additivity, conjugate-linearity and Hermitian lemmas.
It does not substitute a supplied matrix for the actual arithmetic form.

For a common E>=0, the theorem requires four actual diagonals >=(32/25)E,
three adjacent norms <=(51/100)E, two next-neighbour norms <=(9/25)E, and
one farthest norm <=(13/50)E. Complex coefficient phases are arbitrary.
Cauchy's scalar norm inequality followed by the SOS certificate yields

    Re RHS(Autocorrelation(sum_i z_i g_i))
       <= -(2/125) E sum_i |z_i|^2,

because 32/25 - 158/125 = 2/125. There is no division by E; E=0 is included.

The narrower diagonal candidate is not automatically applied to arbitrary
four packets. Their support hypotheses and a common energy normalization
must be supplied. The six actual cross-term hypotheses, including fresh
bindings for the pairs involving the fourth packet, must also be supplied.
The new farthest constant 13/50 is a target, NOT an established actual bound.
A dyadic farthest-pair proof would need its n=8 prime-window isolation,
exact prime evaluation, Archimedean estimate and common-shift transports.

## 5. Exact next obligations

1. Replay all required imports and these three Lean modules with the pinned
   Lean 4.33.1 / Mathlib 0df444a360eaa60ab8c11dca51a86af692955474 toolchain;
   inspect each compiler exit and each #print axioms output.
2. Bind four concrete moment-zero packets to the narrower support and common
   energy, and discharge all six actual cross bounds. Do not simply copy
   the three-block receipt to new pairs.
3. Only then classify a concrete four-block theorem as kernel-bound. Even
   that does not supply arbitrary-packet density, global sign, or RH.

## Reproduction

From repository root:

    python -m unittest discover -s research/rh -p test_four_block_comparison_v2.py -v
    python -O -m unittest discover -s research/rh -p test_four_block_comparison_v2.py -v
    python research/rh/four_block_comparison_v2.py

These commands need only Python's standard library. In an already-prepared
pinned Mathlib workspace with the repository import dependencies compiled,
compile RHFourBlockComparisonV2 first; RHFourBlockActualBridgeV2 and
RHNarrowDiagonalUpgradeV2 can then follow. Record exact source hashes,
compiler version, dependency pin, every exit code and axiom output. A
runnerless or zero-step status does not discharge any of these obligations.
