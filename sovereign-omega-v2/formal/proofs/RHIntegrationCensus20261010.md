# AEGIS Ω / Riemann Hypothesis — integration census

**Snapshot date:** 2026-10-10  
**Purpose:** connect the existing RH proof lines by exact source head, separate kernel-checked results from source candidates, and keep the remaining theorem explicit. This is an evidence ledger, not a proof claim.

## 1. Canonical target and current mathematical blocker

The official fork target is `FormalConjectures/Millennium/RiemannHypothesis.lean`, theorem `RiemannHypothesis.riemannHypothesis`.

The strongest restricted-Weil lane reduces RH to the exact universal sign statement:

```lean
UniversalZeroQuadraticNonnegativeV10 :=
  ∀ g : WeilCompactSmoothGV1, WeilMomentConditionsV1 g →
    0 ≤ (∑' rho : RiemannNontrivialZeroIndexV2,
      WeilZeroIndexSummandV1 (WeilAutocorrelationV1 g) rho).re
```

The equivalent arithmetic form is:

```lean
∀ g : WeilCompactSmoothGV1, WeilMomentConditionsV1 g →
  (WeilExplicitRightSideV1 (WeilAutocorrelationV1 g)).re ≤ 0
```

This is the load-bearing residual, not an import typo. The equivalence theorem does not prove the equivalent proposition.

## 2. Main proof spine and evidence status

| Lane | Exact head / PR | Established scope | Status boundary |
|---|---|---|---|
| Restricted-Weil criterion | AEGIS PR [#679](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/679), head `4d7578ef3df6ae4d1bcd6e2eaefeb2f7f5309afe` | `RiemannHypothesis ↔ UniversalZeroQuadraticNonnegativeV10`; 118-module source closure reported locally compiled with no `sorryAx` | Criterion/equivalence only. PR body reports hosted Actions unavailable; not a proof of the universal sign. |
| Narrow finite-window sign | AEGIS PR [#659](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/659), head `46807c98e13398fa884a399e3559e7a9e7f9d5c5` | Unconditional sign for arbitrary moment-zero packets supported in log half-width (1/128) | Finite window only; preserve exact-head receipt before promotion. |
| Wider moment-gain window | AEGIS PR [#682](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/682), head `10800b9a1aaf9cd275b312b751b74e6dda0632f4` | Source producer for radius (1/8) | Draft/source candidate; not all windows. |
| Stronger multi-cell window | AEGIS PR [#683](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/683), head `f8313af917e41a5a56f441447a46cf8ffe97d247` | `RHWindowSevenOver32V1.window_seven_over_32_arithmetic_nonpositive_v1` for (7/32); also `RHWindowNineOver64GlobalizationV14` for (9/64) | Draft/source candidate. Its recorded workflow jobs failed before producing usable step logs; no exact-head Lean receipt is established by those runs. |
| Mellin / zero-sum analytic line | AEGIS PRs [#479](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/479), [#480](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/480), [#488](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/488), [#490](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/490) | Kernel-checked bounded analytic components, zero-sum/height-limit components, Mellin inversion and prime-line identity at their declared heads | These are component results. The actual linear shell bound, full compiled explicit-formula/autocorrelation transport, universal sign and RH remain separate obligations. |
| Restricted test-class reduction | AEGIS PR [#491](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/491), head `dcfa2a51f52d941937a7cb72996d58b2d0ec0f43` | Moment annihilator, four-phase two-point bound, and a countable test-family reduction; PR reports 44 theorem closures without `sorryAx` at that head | Does not prove that the actual zeta form satisfies the universal sign tests. The arithmetic nonpositivity remains open. |
| Direct Li-criterion target | Fork PR [#37](https://github.com/tarikskalic33/formal-conjectures/pull/37) | Routes the official RH target through the Li terminal | Residual is universal Li–Keiper coefficient nonnegativity; not closed. |
| Exact source snapshot | Fork PR [#65](https://github.com/tarikskalic33/formal-conjectures/pull/65), head `a685f8e3f30bf78fb596fbcbabaa6a40bddf939d` | Exact tree equality with source PR #62; its description reports 8/8 workflows green at that snapshot | Evidence/source consolidation only; official target is unchanged and RH is not proved. |

## 3. The finite-window results do not discharge the official residual

The canonical small-window join in `RHSmallWindowCanonicalJoinV1` proves RH only **given**:

```lean
hLarge : ∀ L : ℝ, (693 / 2000 : ℝ) < L →
  WindowArithmeticNonpositiveV1 L
```

The (7/32) producer covers (L le 7/32), where (7/32 = 0.21875). The cutoff (693/2000 = 0.3465) is larger, and—more importantly—the residual quantifies over **every larger window**, without an upper bound. A further isolated finite radius cannot by itself close this universal tail.

The required next mathematical transition is therefore a genuine global assembly/positivity theorem for arbitrary `WeilCompactSmoothGV1` packets (or a proved decomposition into certified packet families with all cross terms controlled). A finite-packet SOS inequality or a criterion equivalence is not that theorem.

## 4. Fork build/import repair — exact-head state

Fork PR [#71](https://github.com/tarikskalic33/formal-conjectures/pull/71), branch `fix/rh-lean-imports-namespaces-copyright-v1):

- Removed the incompatible `module` marker from the official RH file while its imported AEGIS files remain legacy imports.
- Declared explicit Lake roots `RHRestrictedWeilCriterionV13` and `RHSmallWindowCanonicalJoinV1`; the previous `globs = [".+"]` is invalid Lake syntax (`expected glob`).
- Synchronized `lakefile.extract.toml` to `lakefile.toml`, preserving the intentional difference in `weak.google.answer`.
- The exact-head `Test scripts` job and copyright check passed at the latest inspected head `cb4bfd8bd6b0d48e2721022e6456c60280642495`. Lean/cache and AEGIS replay jobs were still running at census time; no successful full build is claimed.

## 5. Integration rule

1. Preserve exact source pins and existing module blobs; do not replace them with stubs or parallel carriers.
2. Admit a theorem only with exact-head Lean compilation and `#print axioms` output; no `sorryAx`.
3. Label finite-window, conditional, source-candidate, locally compiled, and hosted-replayed results separately.
4. Do not mark RH proved until the universal arithmetic/zero-quadratic residual itself has a closed kernel-checked term and the actual official target compiles at that exact head.

**Current disposition:** `RH_PROVEN = FALSE`; the criterion/equivalence and several finite-window/analytic components exist, but the universal sign needed to close RH remains open.
