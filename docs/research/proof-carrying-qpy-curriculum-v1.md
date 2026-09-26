# Proof-Carrying QPY Curriculum v1

Status: **research-only experimental learning infrastructure**.

Authority effect: **NONE**.

## Core idea

A training example is not admitted merely because one simulator produced a plausible label.
It becomes gradient-admissible only when one mathematical object survives independent
representations and verification paths:

1. analytic closed-form oracle;
2. CUDA-Q `qpp-cpu`;
3. PennyLane `default.qubit`;
4. Qiskit `Statevector` after a QPY v17 serialization round-trip;
5. a provenance-bound formal invariant for pure two-qubit product structure.

The pilot benchmark is the already-bound commuting Ising model

`H = 0.7 Z0Z1 + 0.2 Z0 - 0.1 Z1`

with initial state `|++>`.

For every time point, the curriculum records `<X0>`, `<X1>`, the QPY digest,
the coefficient determinant, a product/entangled label, and the exact provenance of
the formal Lean theorem `coeffDet_eq_zero_iff_pureProductCoeffs`.

## Training rule

`NO_GRADIENT_WITHOUT_MULTI_REPRESENTATION_WITNESS`

The v1 rule is deliberately binary:

- all independent representations agree within the existing scaled tolerance and the
  QPY round-trip is exact under the pinned environment -> weight 1,000,000 ppm;
- otherwise -> weight 0 and the bundle fails closed.

This is not a claim that quantum computation improves language-model quality. It is a
method for constructing machine-checkable, representation-diverse reasoning curricula.

## Why QPY matters

QPY preserves the full Qiskit `QuantumCircuit` object model more faithfully than using
OpenQASM as the canonical persistence layer. The v1 workflow pins Qiskit 2.5.2 and emits
QPY format version 17. Each binary artifact is SHA-256 bound in the receipt.

## Generalization target

The protocol is intentionally domain-independent. Future adapters can replace the quantum
witness tuple with other AEGIS evidence producers:

- Lean/Coq theorem + executable numerical oracle;
- Rust/Python/TypeScript parity witnesses;
- RH/Weil finite calculations with exact theorem-bound targets;
- genomics simulations with source-bound experimental contracts;
- entropy/Bernstein/Lyapunov control traces.

The common object is a proof-carrying curriculum record: a training datum whose target,
representation, provenance, falsifiers, and admissibility decision are all replayable.
