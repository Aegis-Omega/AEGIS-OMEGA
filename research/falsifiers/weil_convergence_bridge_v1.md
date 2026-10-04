# AEGIS Ω — Weil Convergence Bridge v1 falsifier contract

Status: preregistered executable proof-tool contract. This artifact does **not** claim the Riemann Hypothesis is proved.

## Target

Convert the analytically valid implication

```text
finite lower bound + target-approximation bound
    -> conditional pointwise non-negativity
```

into a deterministic AEGIS verifier and expose the remaining global theorem obligations instead of laundering them into a proof claim.

For a test function `f` and cutoff `R`, the local kernel checks exact rational premises corresponding to

```text
Q_R(f) >= -epsilon_R ||f||^2
```

and the algebraic consequence of a separately supplied approximation premise

```text
|Q_W(f) - Q_R(f)| <= delta_R.
```

When `Q_R(f) - delta_R >= 0`, the implication `Q_W(f) >= 0` is algebraically valid **if the approximation premise is true**. v1 therefore records this as a verified inference with an open independent-premise obligation; it does not promote the premise root into mathematical truth.

## Fail-closed invariants

1. `WeilBridgeReceipt != RH proof`.
2. Model output, literature citation, hash integrity, ProofTrace integrity, and a caller-supplied premise root are evidence only.
3. `ASSUME_RH`, `ASSUME_GLOBAL_WEIL_POSITIVITY`, `ASSUME_ALL_ZETA_ZEROS_ON_CRITICAL_LINE`, and equivalent target assumptions are forbidden as load-bearing assumptions.
4. Exact arithmetic uses reduced rational numbers; binary floating point is not accepted by the proof kernel.
5. A violated finite lower bound is rejected.
6. A finite family of test functions never implies global Weil positivity by enumeration alone.
7. Density, continuity, and universal-domain coverage roots are not accepted as self-authenticating theorem proofs.
8. Global closure remains `OPEN_KERNEL_GLOBALIZATION_REQUIRED` until an independent machine-verifiable theorem checker is integrated and re-run.
9. Every ProofTrace attachment is a `VERIFIER / NONE / T2` span and cannot advance control state.
10. Every receipt is deterministic and semantic tampering changes its root.

## Explicit open theorem

The production target after v1 is a fixed-kernel globalization checker establishing a statement of the form

```text
DenseFamilyPositivity
AND ContinuityOfWeilForm
AND UniversalCoverageOfAdmissibleTestSpace
-> GlobalWeilPositivity
```

without assuming RH or an equivalent target statement.

Only after that theorem is independently machine-checked, and its premises are themselves closed, may a future version evaluate the classical equivalence

```text
GlobalWeilPositivity <-> RH.
```

v1 deliberately refuses that promotion.

## Expected RED

Before `harness/sdk/weil_convergence_bridge.py` exists, the dedicated test suite must fail at import with `ModuleNotFoundError`.

## Expected GREEN

After implementation, all dedicated falsifiers and inherited ProofTrace falsifiers must pass on the exact candidate SHA. A GREEN workflow certifies only this software contract, not RH.
