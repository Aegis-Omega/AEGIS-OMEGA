# AEGIS Ω — Gravity/Quantum Authority V1

Status: **DRAFT / evidence-only / authority_effect=NONE**

Parent: PR #535 `research/cross-boundary-authority-v1` at
`450a641a5466702ed18b4d4277efeefbbd9c9a01`.

This child lane registers bounded domain verifiers without changing the parent
cross-boundary semantics.

## Closed locally before repository publication

- D2 source formula replay: Kryhin–Sudhir PRL 134, 061501,
  arXiv:2309.09105v2, Appendix E Eq. 87/89/90.
- Executable policy evaluator: a policy digest alone cannot authorize admission.
- F2b theorem source: for a 2x2 pure-state coefficient matrix,
  `det(A)=0` iff its coefficients factor as `a_ij=x_i y_j`.
- Cross-boundary regressions preserve the #535 rule that a passing bridge yields
  only `ELIGIBLE_FOR_SEPARATE_TARGET_TRANSITION_ONLY`.

## Current fail-closed state

```text
D2_MODEL_FORMULA            = LOCALLY_REPRODUCED
F2B_LEAN_SOURCE             = PREPARED
F2B_KERNEL_REPLAY           = PENDING_HOSTED_EXECUTION
PHYSICAL_MEASUREMENT        = NOT_PERFORMED
NUISANCE_CONTROL_RECEIPT    = NOT_PERFORMED
INDEPENDENT_REPLICATION     = NOT_PERFORMED
GRAVITY_QUANTIZED           = NOT_ESTABLISHED
QUANTUM_GRAVITY_PROVEN      = NOT_ESTABLISHED
REPOSITORY_ADMISSION        = NOT_GRANTED
AUTHORITY_EFFECT            = NONE
```

## Interpretation boundary

A theorem about finite two-qubit coefficient factorization is formal evidence.
A numerical replay of a published stochastic-gravity spectrum is model evidence.
A physical measurement receipt is empirical evidence.

None can be silently coerced into another.

Even if every registered bridge verifier returns PASS, #535 semantics permit only
a separate target-status transition. No verifier in this lane mutates
`gravity_quantized`, grants production authority, or establishes a complete
fundamental theory of quantum gravity.

## D2 source boundary

The D2 implementation is restricted to the two-oscillator Newtonian-limit model
in Kryhin and Sudhir, *Distinguishable Consequence of Classical Gravity on
Quantum Matter*, Phys. Rev. Lett. 134, 061501 (2025),
arXiv:2309.09105v2.

It numerically checks the additional-zero/phase-flip structure of Eq. 87 against
the high-Q approximation Eq. 89 under the Eq. 90 visibility regime. This is not
laboratory evidence.

## F2b kernel boundary

The dedicated workflow pins:

- Lean 4.33.1 release SHA-256
  `890afd185370f85666025b883914ab4f4b339136f8c96167b69cfb62aecaf235`;
- Mathlib
  `0df444a360eaa60ab8c11dca51a86af692955474`.

Until that exact workflow actually executes the Lean steps successfully,
`F2B_KERNEL_REPLAY` remains **NOT ESTABLISHED**.
