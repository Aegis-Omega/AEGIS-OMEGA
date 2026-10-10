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

## 6. Previously disconnected lanes now inventoried (2026-10-10)

This section extends the earlier inventory: a finite-window producer, a conditional algebra lemma, and a kernel-replayed analytic component are different evidence classes and are not interchangeable.

| Lane | Exact source reference | What is genuinely present | Admission status / limitation |
|---|---|---|---|
| Autocorrelation closure | AEGIS [#493](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/493), head `f10d066152dd07fcbe6497566213d91f29e68c5a` | The actual Weil autocorrelation is put into the compact-smooth carrier and existing arithmetic convergence is applied. The PR reports hosted run 34728365554 SUCCESS and 29 theorem closures with only the standard Lean axioms and no `sorryAx`. | Component verified at that exact historical head; it proves no sign. Replay again on the eventual combined head. |
| Paired Hadamard / zero-side sum | AEGIS [#519](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/519), head `53bc21debc3a944489f890b9eceff94126c35ab7`; [#527](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/527), head `77adaa32bbedd32c765409b550b564413094b520` | Multiplicity-aware paired Hadamard identity and fused kernel tsum; reported exact-head hosted SUCCESS for runs 35283590860 and 35284851626, respectively. | Verified analytic/series components only. They do not establish the sign of the complete zero quadratic. |
| Mellin decay / shell synthesis | AEGIS [#479](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/479), head `59c26b825fa248d070e42fae04ccf7a15b285084`; [#480](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/480), head `6ec8bb0ee39c462a5b544620b5ad2648c52ecb1e`; [#481](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/481), head `c85a58ca753e5d99fc9f117e0dc481e1f2cf0bde` | Conditional shell-synthesis theorem and compact-smooth Mellin cubic decay have reported exact-head hosted SUCCESS on #479/#480. | The producer for an actual uniform linear shell multiplicity bound in #481 is still an obligation; a bound for a generic compact-smooth Mellin transform is not by itself the bound for the actual zeta-zero shell. |
| Restricted-WEIL criterion source replay | AEGIS [#698](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/698), source payload `b6ec25c76f0c92b1fd52371b46311e3762866ec7`; fork verifier [#49](https://github.com/tarikskalic33/formal-conjectures/pull/49), verifier `0583a8e8ff8a84aeee2c69b8b2f0f6b28121cd4a` | Independent exact-head replay reported SUCCESS (run 36477556808): 91/91 source blobs bound and 91/91 local Lean modules compiled; headline axiom audit standard-only, no `sorryAx`. | Establishes the conditional/equivalence criterion interface, not the universal sign premise and not RH. |
| Small-window sign | AEGIS [#659](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/659), head `46807c98e13398fa884a399e3559e7a9e7f9d5c5` | Source declares unconditional nonpositivity for every repository packet satisfying moments and support half-width `1/128`, with a dedicated pinned Lean workflow. | Keep finite-width scope; must be replayed on any consolidated exact head before claiming it green there. |
| Nine-packet (`q=33/16`) line | AEGIS [#661](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/661), head `ecb39e85e9fa35d4bccd01fc1a23a948ae9043c1`; fine diagonal [#664](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/664), head `ca24dfa466d5d4c5eaec1b269f2f0a21a64a5c5c`; strengthened margin [#665](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/665), head `9768a496f4fb489045226f4c5ebb8af8f29e9a33` | Exact-rational preflight lists the integer windows at gaps 1–8; the candidate fine diagonal is `5671/3200`, and the source targets nine-packet margin `1083/640`. | #661 explicitly records workflow `steps=[]` at its inspected initial head, therefore NOT_EXECUTED, not Lean-GREEN. #664/#665 are source candidates over a reported kernel-GREEN parent; this is a finite family and does not globalize. |
| Ten-packet (`q=33/16`) line | AEGIS [#671](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/671), head `39c2851ae698542b4002d1f1ca5f5d24ddf1e240`; gap ten [#672](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/672), head `3df9ad4530072b300fbab96ace0c30b16bbd8fd4`; lattice transport [#677](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/677), head `8ac133a165f6d9da7a306d9b9840711cffa80ff2` | Explicit ten-packet candidate uses diagonal `5671/3200`, gaps 1–8 at `1/100`, gap 9 at `57/100`; gap 10 targets `837/3700`. | #671 and #672 are source candidates, #677 is a transport lemma based on the gap-ten bound; no admitted concrete global theorem is claimed. |
| Eleven-packet SOS line | AEGIS [#674](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/674), exact-rational preflight head `2d09039b05cc57d18673bfb5f87e9b1dbad837d9`; [#675](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/675), Lean SOS head `d5fe8333bfb39c1cf9f62b4277ca76a23d94d468`; [#676](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/676), conditional complex bridge head `2b9da4e3a4029c7eca3cc3f0db88831c01743eca` | Rational comparison has target margin `106083/118400` under stated diagonal/cross-term bounds. | #675 itself says it does not bind the actual repository B form or a concrete eleven-packet. #676 remains conditional and explicitly says no actual B expansion/lattice binding/globalization. |
| Width-dependent dyadic tower / log(2)-log(3) density | Fork [#65](https://github.com/tarikskalic33/formal-conjectures/pull/65), tree-identical source reconstruction of #62; exact module `FormalConjectures/Millennium/RHSnowflakeLog23.lean` on `proof/rh-main-exact-tree-consolidation-v1` | Kernel-checkable arithmetic-topological facts include irrational `log 2 / log 3` and density of the generated additive subgroup; the prime-only lane joins theta/psi discrepancy by a bounded higher-prime-power correction. | Density alone does not transfer sign unless nonnegativity is proved on the dense subgroup for the same fixed admissible packet and the actual quadratic is continuous. The fork's `RH_GLOBALIZATION_OBSTRUCTION_V1.md` explicitly isolates this logical gap with an analytic countermodel (not a counterexample to RH). |
| Prime-only growth terminal | Fork [#62](https://github.com/tarikskalic33/formal-conjectures/pull/62), head `78cf37e2f837dcaac1fface0ea1b7c04804f70a1` | Exact Chebyshev identity and bounded higher-prime-power perturbation connect the prime-only orbit with the full Chebyshev orbit. | Terminal still requires prime-only subexponential growth and the actual identity/bounded-remainder connection from that arithmetic orbit to the canonical zero-translation kernel. It is a viable independent proof route, not a closed proof. |
| Li-criterion terminal | Fork [#37](https://github.com/tarikskalic33/formal-conjectures/pull/37), head `645a8858f386b1e391097d90a129ee6f1a1f5b3b` | Targets the official Formal Conjectures theorem directly through the Li-criterion provider. | Residual is `∀ n : ℕ, 0 ≤ (LiCriterion.taylorCoeff LiCriterion.riemannXi n).re`; this coefficient positivity producer is still missing. |

## 7. Exact-head CI disposition for the current integration candidates

- AEGIS #721 head `a9c4345d42f342e91c20d3397cf6dcc43a898385`: GitHub reports failed runs for the new restricted-Weil workflow (`38005214655`), Kernel One (`38005214504`), Dependency Review (`38005214480`), and Coq Formal Attestation (`38005214476`). The workflow job endpoints returned `steps=[]` and log downloads returned `BlobNotFound`; therefore these runs do **not** identify a Lean source error. They also do not provide a successful kernel replay. A retry request was accepted but did not return a usable job record at the time of this census.
- AEGIS #683 head `f8313af917e41a5a56f441447a46cf8ffe97d247`: its Kernel One, cumulative Mellin, emergency Lean replay, Formal Conjectures bridge, and Coq runs are likewise reported failed with no retrievable step logs. Do not label these heads Lean-RED from runner-level failures alone.
- AEGIS #698 / fork #49 is the current positive replay receipt for the 91-module restricted-Weil *criterion* payload. Keep its source hash and replay verifier hash coupled; do not transfer that receipt to #721 or #683.

## 8. Integration ordering and the actual proof obligations

1. **Use one proof spine, not one mega-merge of unrelated history.** Pin the official target, the external Li provider, Mathlib, Lean, source blobs, and every source receipt. Import source modules by dependency graph rather than by PR creation order. Keep the #698 restricted-Weil closure, #493 autocorrelation closure, fixed-line/Hadamard series modules, the small-window families, the packet/SOS branches, and the prime-only/Li routes identifiable as separate producers.
2. **Make every producer exact-head reproducible.** For each module in the chosen closure, check out its recorded SHA/blob, compile in dependency-topological order, capture `#print axioms`, reject `sorryAx`, and run the official `RiemannHypothesis.lean` target at that same assembled commit. Historical green results validate historical bytes only.
3. **Do not derive global positivity from adaptive-width packet results.** The fixed-width universal quantifier cannot be discharged by a theorem whose admissible width shrinks as the number of shifts grows. The missing bridge must provide a fixed admissible approximation of arbitrary test packets with convergence of the actual Weil quadratic and all cross terms controlled, or a new direct universal inequality for the actual `B` form.
4. **Do not substitute a candidate SOS matrix for actual analytic input.** #671/#672/#675/#676 list numerical/algebraic bounds, but those constants are useful only after the individual gap estimates are tied to the actual repository kernel at the same exact head.
5. **The next mathematical work item is the universal-sign/globalization theorem**, not another import-only change or an eleventh finite family. In parallel, the analytic route must close the actual shell multiplicity bound and connect the actual autocorrelation to the Mellin-decay estimates; the Li route must produce all Li–Keiper coefficient signs. These are alternative proof terminals, not premises that may be assumed.

**Updated disposition:** no repository evidence inspected here supplies a closed, unconditional term for `UniversalZeroQuadraticNonnegativeV10` or the Li coefficient family. The inventory is now broader, but the mathematical conclusion remains `RH_PROVEN = FALSE` until one of those genuine terminal producers is kernel-checked.
