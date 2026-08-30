# Independent check of the finite prime-power phase / sign normalisation

```
EPISTEMIC_STATUS : INDEPENDENT_RECONSTRUCTION + INTERVAL_CERTIFIED
SCOPE            : prime powers p^k ≤ 2·10⁴, Arb at 300 bits
NORMALIZATION    : weight w(p,k) = log p · p^{−k/2}
                   entry coordinate x = k on [0, m], m = max{ j : p^j ≤ P }
                   phase S(x) = sin(2πx/m)   (odd about x = m/2)
```

This reconstructs the reported finite prime-phase identities from their
statements alone. The artefacts they were reported in
(`integration/rh-weil-evidence-v1`, `da051ee2`, `4f35cf49`,
`FinitePrimePhase.v`) are **not reachable**: the branch and both commits are
absent from the remote, and none of the four named files exist on any `weil`,
`rh`, or `main` ref. This file therefore checks the *statements*, not the
original formalisation.

**Declared, not derived**

| symbol | status |
|---|---|
| `S(x) = sin(2πx/m)` | **chosen** — the smallest nontrivial phase satisfying the reported premise; the original `S` is unknown |
| `x = k`, segment `[0, m]` | **chosen** placement of a prime-power entry |
| `P` ladder | chosen grid; no claim of optimality |
| odd-reflection premise | **assumed**, exactly as reported; not established here |

**Not claimed**

- any statement about the Riemann Hypothesis
- that this parameterisation is the one used in `FinitePrimePhase.v`
- that the odd-reflection premise holds for the true Weil off-diagonal phase

## What reproduces

| reported identity | result |
|---|---|
| `m(1 − y/L) = m − my/L` | holds, interval-exact |
| `S(m − x) = −S(x)` under the premise | holds for all `0 ≤ x ≤ m`, `m ∈ {2,3,5,8,13}` |
| direct = complementary off-diagonal | `direct + complementary ∈ [±1.87e−86]` at `P = 2·10⁴`, 2328 terms |
| induction to arbitrary finite sums | all 2328 truncations cancel, 0 failures |

## Finding 1 — the finite-sum lift carries no arithmetic content

Replacing the arithmetic weights `log p · p^{−k/2}` with arbitrary numbers
drawn from `[−10⁶, 10⁶]` leaves the cancellation intact (4 trials × 500
weights). Perturbing the phase so it is no longer odd about `m/2` destroys it
immediately.

The lift from one prime-power term to a finite sum is therefore **linearity,
not arithmetic**: if every term negates under the reflection, so does any
weighted sum, whatever the weights. The primes do not participate. All of the
content sits in the premise `S(m − x) = −S(x)`, which is assumed rather than
established.

This is recorded so that a `W0→W7` entry reading "finite sums closed" is not
mistaken for progress on the hard direction.

## Finding 2 — the index set is not closed under the reflection

For the index set `{ p^k ≤ P, 1 ≤ k ≤ m }`, the reflection `k ↦ m − k` lands
outside it for:

| `P` | terms | reflect inside | reflect **outside** |
|---|---|---|---|
| 20 | 12 | 4 | 8 (66.7 %) |
| 100 | 35 | 10 | 25 (71.4 %) |
| 1 000 | 193 | 25 | 168 (87.0 %) |
| 20 000 | 2328 | 66 | **2262 (97.2 %)** |

The 2262 escaping terms are exactly `π(20000)` — the top power of every prime
maps to `k = 0`, which is not a prime power. For every `p > √P` we have
`m = 1`, so the only term `k = 1` leaves the set.

Two readings diverge here, and they are not equivalent:

- **term-wise** — `S` evaluated at the complementary coordinate over the same
  index set. Closure is irrelevant; the identity is the linearity above. This
  is what reproduces.
- **re-indexing** — the sum taken over reflected indices. The index set is not
  reflection-closed, and the identity needs either `k = 0` included in the
  range or an explicit boundary correction.

Whether `FinitePrimePhase.v` sums over `0..m` or `1..m` decides which applies.

## Reproduce

```bash
python3 research/rh/finite_prime_phase_independent.py
```

Receipt: `research/rh/receipts/finite_prime_phase_independent_p20000.json`
