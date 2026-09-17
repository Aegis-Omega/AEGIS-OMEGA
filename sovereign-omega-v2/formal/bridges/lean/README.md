# Modulo contract → cyclic limits (V1)

Four kernel-checked Lean 4 modules. Every theorem below was compiled with
`lake env lean` against Lean `v4.34.0` / Mathlib `78f7ceb7`, exit 0, and every
`#print axioms` line reports only `propext`, `Classical.choice`, `Quot.sound`
(or fewer). No `sorryAx` anywhere.

These are the first Lean modules on this lane; the surrounding Weil work here is
Coq. They are inert — no workflow consumes them, and they are branched off
`proof/weil-arch-tail-order-v1` so that lane and its PR #322 stay untouched.

## What this is

`AEGIS_MODULO_CONTRACT_V1` states a semantic factorization rule:

> `R(x) = F(x) mod m` may be read as a target `T` only if `R x = R y → T x = T y`.

These modules do two things with it: prove the ring theorem the contract asserts
about the live `core_matrix.py` write paths, and apply the factorization rule to
the arithmetic objects the Weil explicit formula actually needs.

## What this is NOT

**This is not a proof of the Riemann Hypothesis, and contains no step toward one.**

Most of the results below are *negative* — they say what a construction
**cannot** reach. A negative result cannot yield RH. Stated precisely, for the
record:

| Claim | Status |
|---|---|
| `RiemannHypothesis` proven | **NO** — no theorem in this PR, or anywhere in this repository, concludes `RiemannHypothesis` |
| Abjad/residue encoding recovers the prime side | **REFUTED** here (`no_abjad_function_gives_vonMangoldt`) |
| A cyclic dilation filter reaches the pole moment `s = 1` | **REFUTED** here (`product_of_cyclic_never_annihilates_pole_moment`) |
| `WeilCompactSmoothNegativityV1` (the Weil positivity criterion) | **OPEN** — restated on lane `#493`, never proven |
| explicit-formula identity, global Weil sign | **OPEN** |
| authority effect on `main` / governance | **NONE** |

The useful content of a no-go theorem is that it closes a search direction.
That is what these are: the abjad/cyclic direction is closed, mechanically,
so no further effort goes into it.

## Modules

### `AegisModuloRingV1.lean` — 7 theorems

The fixed-width ring theorem. For a region of `L` bytes holding records of `w`
bytes, the slot representation `w * (n % (L / w))` and the byte-ring shortcut
`(w * n) % L` agree **iff** `w ∣ L` (`byteRing_eq_slot_iff_dvd`). The shipped
`FINITE_REPLAY` only spot-checks `w ∈ [2,32]`; this is the general statement.

Applied to the two live `core_matrix.py` sites at the 4 GB profile, both of
which fail the divisibility condition:

- `m1_width_does_not_divide_region` : `¬ (40 ∣ 2147483648)`
- `m2_width_does_not_divide_region` : `¬ (8 ∣ 1288490188)`
- `m1_drift_at_wrap` : at the wrap index the grid expects offset `0`, the byte
  ring lands at `2147483640` — and `byteRing_overruns_region_at_wrap` shows the
  record then overruns the region, so M1's `end_pos <= len(state)` guard
  discards it silently.

`m1_drift_at_wrap` depends on **no axioms at all**.

No fix to `core_matrix.py` is included — that path is live on Cloud Run and
changing it changes the memory layout. This PR only states the arithmetic.

### `AbjadFactorizationV1.lean` — 4 theorems

The abjad encoder's entire arithmetic content is `n % 36` (`digital_root = n%9`,
`dodecagon_node = n%12`, `opposite = (node+6)%12`; `9 ∣ 36`, `12 ∣ 36`, and
`ℤ/36 → ℤ/9 × ℤ/12` is injective).

- `factors_iff_constant_on_fibres` — the contract rule, as an iff.
- `vonMangoldt_not_factors` — `5` and `41` are both prime and share *every*
  abjad output, yet `Λ 5 = log 5 ≠ log 41 = Λ 41`.
- `primality_not_factors` — `5` and `77` share every abjad output; `77 = 7·11`.
- `no_abjad_function_gives_vonMangoldt` — therefore **no** function of the abjad
  encoding reproduces `Λ`, so the prime side `∑ Λ(n) f(n)` is not recoverable
  from abjad data.

### `ResidueClassFactorizationV1.lean` — 1 theorem

Where residue information *does* legitimately enter number theory: a Dirichlet
character is by construction a function on `ZMod q`, so it descends along the
residue map (`character_factors_through_residue`). Mathlib's
`DirichletCharacter.sum_char_inv_mul_char_eq` then writes a residue-class
indicator as a combination of such functions. This is cited, not re-derived.

It is not a shortcut: it replaces one contour problem for `ζ` with `φ(q)`
contour problems, one per character, and its conclusion is GRH.

### `CyclicFilterLimitV1.lean` — 5 theorems

The repository's `WeilMomentAnnihilatorV1` filter `f(x) − 3f(2x) + 2f(4x)` has
Mellin multiplier `(1−u)(1−2u)` in `u = 2^(−s)`, so its two roots are the two
Weil moments: `u = 1 ↔ s = 0` (reflection) and `u = 1/2 ↔ s = 1` (the **pole**
of `ζ`). An n-fold cyclic filter `f(x) − f(2ⁿx)` has multiplier `uⁿ − 1`, whose
roots are exactly the n-th roots of unity — this is the 6/12-cycle ring, with
the `+6` phase step being `u ↦ −u`.

- `cyclic_annihilates_reflection_moment` — cyclic filters do reach `s = 0`.
- `half_not_root_of_unity` — roots of unity lie **on** the unit circle; `1/2` is
  strictly inside it.
- `cyclic_never_annihilates_pole_moment` — so no cycle length and no number of
  phase steps reaches `s = 1`.
- `repository_multiplier_annihilates_pole_moment` — the repo's filter does reach
  it, via its second factor, which is **not** cyclotomic.
- `product_of_cyclic_never_annihilates_pole_moment` — and no product of cyclic
  multipliers reaches it either.

In one line: the cyclic structure is real, it is genuinely a ring, and it is
provably blind to the pole. Rotation cannot leave the unit circle.

## Verification

```
cd <mathlib4 checkout @ 78f7ceb7>            # lean-toolchain: leanprover/lean4:v4.34.0
cp sovereign-omega-v2/formal/bridges/lean/*.lean scratch/
lake env lean scratch/AegisModuloRingV1.lean
lake env lean scratch/AbjadFactorizationV1.lean
lake env lean scratch/ResidueClassFactorizationV1.lean
lake env lean scratch/CyclicFilterLimitV1.lean
```

Each exits 0 and prints its `#print axioms` block.

`ResidueClassFactorizationV1.lean` additionally compiles unchanged on Lean
`v4.33.1` / Mathlib `0df444a3` (the `#493` lane toolchain).

## Source hashes (sha256)

```
0d45197842534307f2092ef17970c167df8fdd998d40b58819cf3331a8d6cb7d  AegisModuloRingV1.lean
db893663ba81e2741aebf2680f4562307900c893c46ee89f9092a27af2e374e3  AbjadFactorizationV1.lean
197fecf442c4dda6764434b54bea64578bfd99ad0c6ca29edfbd2e91014fa519  ResidueClassFactorizationV1.lean
997bb2bcb94ed76874becbec42392cdc71e351ee7cf05a74088e4702cdbe2af2  CyclicFilterLimitV1.lean
```

## Not included here

The `#493` prime-side work (`WeilPrimeReindexV1.lean`, the sharpened support
hypothesis `0 ∉ tsupport f`, the `n+1 ↔ m≥2` reindex) is **not** in this PR. It
is based on `f10d066152dd07fcbe6497566213d91f29e68c5a` and imports
`WeilPrimeSummabilityV1`, which does not exist on this branch. It belongs on its
own lane and is not grafted here.
