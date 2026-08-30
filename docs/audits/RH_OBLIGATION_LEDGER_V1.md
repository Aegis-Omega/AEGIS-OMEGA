# RH Obligation Ledger V1

Authority: FAIL-CLOSED RESEARCH/FORMAL INTEGRATION LEDGER

Final verdict: `RH_NOT_PROVEN`

The machine-readable authority source is `research/rh/proof-obligations-v1.json`, loaded by `harness/sdk/rh_obligation_gate.py`. This prose is explanatory only and cannot promote an obligation.

| ID | Obligation | State | Load-bearing boundary |
|---|---|---|---|
| W0 | Xi / Weil setup | PARTIALLY_FORMALIZED | Concrete criterion closure not machine-bound |
| W1 | Finite prime-phase boundary | BLOCKED | Reflection/index-set boundary requires explicit theorem/boundary correction |
| W2 | Constructive trig/calculus | OPEN | Prime diagonal constructive witness/transport |
| W3 | Archimedean singularity lane | PARTIALLY_FORMALIZED | Analytic reasoning not pre-promoted to proof-kernel closure |
| W4 | Gaussian tail theorem | OPEN | Real-analysis theorem behind QForm error budget |
| W5 | Composite trapezoid theorem | OPEN | Rigorous quadrature remainder in authority lane |
| W6 | Guinand-Weil/operator identity | OPEN | Concrete formula-to-Weil semantics |
| W7 | Continuous Archimedean order | OPEN | Finite Gram PSD is not the continuous theorem |
| W8 | Density/continuity/coverage | OPEN | Approximation and universal test-space coverage |
| W9 | Concrete Weil criterion | OPEN | Actual global Weil positivity and criterion equivalence |
| W10 | Final Riemann Hypothesis | BLOCKED | Requires W9 and full dependency closure |

## Finite-to-global shortcut correction

`FTG-DENSITY-ALONE-COUNTEREXAMPLE-V1` is now an executable exact-rational regression. It refutes only the claim

`density of increasing finite stages + positivity on every finite stage => positivity at closure points`

when no continuity/lower-semicontinuity/closed-form hypothesis is supplied.

The witness uses `H = l2(N)`, dense `c00`, `u*_k = 2^-k`, domain `D = c00 (+) span{u*}`, and

`Q(v + alpha*u*) = ||v||_2^2 - alpha^2`.

Every coordinate stage `V_N` is positive because `Q|V_N = ||.||_2^2`, while `Q(u*) = -1` and the truncations converge to `u*` with exact tail norm squared `1/(3*4^N)`.

This does **not** refute the standard theorem that continuity of a quadratic form plus density extends nonnegativity from a dense subspace to its closure. The missing continuity/closed-form hypothesis is precisely the load-bearing issue. The deterministic receipt is `research/rh/receipts/finite_to_global_counterexample_v1.json`, authority class `EXACT_RATIONAL_REGRESSION_NOT_PROOF_ASSISTANT`.

## Highest-leverage attack order

The integration lane should prioritize theorem obligations whose closure unlocks multiple downstream edges:

1. W2 constructive trig/calculus;
2. W4 Gaussian tail theorem;
3. W5 composite trapezoid theorem;
4. W7 continuous Archimedean representation/order;
5. W6 concrete Guinand-Weil/operator identity;
6. W8 density/continuity/coverage;
7. W9 concrete Weil criterion/global positivity;
8. W10 final proof-kernel theorem.

The ordering is a research heuristic, not mathematical authority. An RKHS decomposition is therefore tracked as a candidate attack on W9/global positivity, not silently relabelled as W5 in this refined DAG.

## Non-promotion rule

The following do not close an obligation by themselves:

- finite-dimensional PSD;
- floating-point eigenvalues;
- Arb/interval calculations unless the obligation is specifically finite arithmetic;
- CI success;
- model/agent consensus;
- literature citation;
- PR description;
- deterministic receipt without theorem semantics;
- exact source identity without proof closure.

Only an independently replayed proof-kernel/formal receipt matching the obligation semantics may justify a transition to `FORMALLY_VERIFIED`.
