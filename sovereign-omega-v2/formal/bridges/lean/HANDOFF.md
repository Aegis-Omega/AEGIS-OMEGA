# HANDOFF — Weil / RH formalization lane

Pick this up cold. Everything below was verified by running it, not read from docs.
Where a doc disagrees with what you observe, what you observe wins.

**Last verified: 2026-09-20. Branch `proof/weil-arch-tail-order-lean-v1`, head `82827062`, PR #510 (draft).**

---

## 0. Read this first: what this lane is and is not

Fourteen Lean 4 modules, 138 theorems, zero `sorry`, every printed theorem closing over
`{propext, Classical.choice, Quot.sound}` only.

**No theorem here proves the Riemann Hypothesis, and this chain will not reach it by
continuing as it has been going.** Weil's criterion is an *equivalence* with RH, so the
final step of any such decomposition **is RH itself**. What has been closed so far is the
tractable infrastructure around a gap that nothing has touched. Specifically:

- `ANALYTIC_DIAGONAL_LOWER_V1` has not moved since this lane started.
- The global Weil sign has not moved.
- `universal_arithmetic_nonpositivity` (lane #491) has not moved, and *is* RH.

If you pick this up expecting a ladder with a finite number of rungs left, stop. There are at
least five obligations remaining and the last one is the whole problem. That is stated here so
nobody re-derives the disappointment.

**What is genuinely valuable here are the no-go theorems** (§4). They close search directions
and are, as far as we know, not formalized anywhere else.

---

## 1. Environment rebuild (the perishable part — do this first)

The container is ephemeral and gets reclaimed. Nothing below is pinned by the repo. Budget
~40 min, mostly `lake exe cache get`.

```bash
# 1. elan + Lean 4.33.1
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y
export PATH="/root/.elan/bin:$PATH"

# 2. Mathlib pinned to the lane commit
git clone --filter=blob:none https://github.com/leanprover-community/mathlib4 ~/mathlib4-433
cd ~/mathlib4-433
git checkout 0df444a360eaa60ab8c11dca51a86af692955474   # "chore: bump toolchain to v4.33.1"
lake exe cache get                                       # ~8700 oleans

# 3. Save LEAN_PATH once
SP=/tmp/sp; mkdir -p $SP
lake env printenv LEAN_PATH > $SP/leanpath.txt
```

Verify: `lean --version` → `4.33.1 … commit 819816b2e0a3bf405af45ae5c7af2491d8f5bee6`,
and `find ~/mathlib4-433/.lake -name '*.olean' | wc -l` → ~8702.

### Building a module

`lean -o` requires the input under the cwd root, so **cd into the scratchpad first**:

```bash
SP=/tmp/sp; export PATH="/root/.elan/bin:$PATH"; LP="$SP:$(cat $SP/leanpath.txt)"
cd $SP && env LEAN_PATH="$LP" LEAN_NUM_THREADS=2 lean Module.lean
```

A module that others import needs its olean built first:

```bash
cd $SP && env LEAN_PATH="$LP" lean -o WeilMomentKillerConstructionV1.olean WeilMomentKillerConstructionV1.lean
```

Success = zero output plus the `#print axioms` lines. Any `sorryAx` in those lines is a failure
even if the build exits 0.

### A second toolchain exists

Five modules (`WeilPoleTermV1`, `AegisModuloRingV1`, `AbjadFactorizationV1`,
`ResidueClassFactorizationV1`, `CyclicFilterLimitV1`) were built on **Lean 4.34.0 / Mathlib
`78f7ceb7`**. Only 4.33.1 was rebuilt in the last session. If you touch those five, you need
that second toolchain too.

---

## 2. Module map

All under `sovereign-omega-v2/formal/bridges/lean/`.

| Module | What it proves |
|---|---|
| `WeilArchimedeanCothTailV1` | `∫_{Ioi w} du/sinh u = log((1+e^{-w})/(1-e^{-w}))`; `6 log 2 <` tail at `w=1/32` |
| `WeilArchimedeanCothTailV1_Control` | same tail `< 7 log 2` (two-sided, so the bound is not slack) |
| `WeilDiagonalConstantFromCothTailV1` | `103/100 < diagonalConstantV1` with the **real** tail, stand-in removed |
| `WeilArchimedeanPacketWitnessV1` | width-1/32 packet; and that it **cannot** satisfy the moments |
| `WeilMomentKillerConstructionV1` | `φ = ψ'+ψ''` kills both additive moments; `φ≡0 ⟹ ψ≡0` |
| `WeilLogChangeOfVariablesV1` | `x = e^u` transport; **`WeilMomentConditionsV1` discharged** |
| `WeilDigammaIntegralReductionV1` (+ `_Control`) | Gauss digamma integral, series half only |
| `WeilPoleTermV1` | explicit-formula pole term derived from `riemannZeta` |
| `AbjadTriadicPhaseCorrespondenceV1` | four-phase ↔ abjad-triadic; and the prime no-go |
| `AbjadFactorizationV1`, `CyclicFilterLimitV1`, `ResidueClassFactorizationV1` | no-go results |
| `AegisModuloRingV1` | `w*(n%(L/w)) = (w*n)%L` iff `w ∣ L`; live `core_matrix.py` drift |

---

## 3. State of the archimedean chain

`WeilArchimedeanPacketWitnessV1` named three steps needed for `ArchimedeanPacketReductionV1`:

| Step | Status |
|---|---|
| (i) packet with log-support in `[-1/32, 1/32]` | **PROVED** (`gWitness_log_support`) |
| (ii) change of variables `x = e^u` | **PROVED** (`WeilLogChangeOfVariablesV1`) |
| (iii) autocorrelation vanishing outside log-support | **OPEN** |
| `ArchimedeanPacketReductionV1` constructed (`arch = D * nrm2`) | **OPEN**, never built |
| `ANALYTIC_DIAGONAL_LOWER_V1` | **OPEN** |
| off-diagonal blocks of the three-block decomposition | **OPEN** |
| global Weil sign | **OPEN** — needs the prime side, which §4 shows has no shortcut |
| RH | **OPEN** — and is the global sign over a sufficient class |

`gWitness` (in `WeilLogChangeOfVariablesV1`) carries (i) and (ii) simultaneously: it is in
`WeilCompactSmoothGV1` (smooth, compact support, `tsupport ⊆ Ioi 0` — all proved), its support
sits in the window, both moment conditions vanish, and `gWitness_ne_zero` rules out the trivial
witness. The bump packet of `WeilArchimedeanPacketWitnessV1` is superseded.

Step (iii) is **harder than (i) and (ii)**: it is a statement about the convolution
`WeilAutocorrelationV1 g x = ∫ y in Ioi 0, g(x*y) * star(g y)`, not a change of variable.

---

## 4. The no-go results (the part worth keeping)

| Theorem | Content |
|---|---|
| `triadic_residue_meets_primes_only_at_three` | the abjad-triadic node set meets the primes in **exactly one point**, `{3}` |
| `no_abjad_function_gives_vonMangoldt` | `Λ` does not descend along abjad (`5`/`41` prime, same abjad, `log 5 ≠ log 41`) |
| `primality_not_factors` | primality does not descend either (`5`/`77`) |
| cyclic filter limit | multiplier `uⁿ−1` has roots **on** the unit circle; the pole moment sits at `u=1/2`, inside it — no cycle length, no phase count, **no product** reaches it |
| `phi0_not_nonneg` | a moment-killed packet **must** change sign — no downstream argument may assume packet positivity |
| `m1_drift_at_wrap` | depends on **no axioms at all**; exact byte offsets for the live M1 config |

`three_is_triadic` exists so the first no-go is not vacuous (intersection is `{3}`, not empty).

---

## 5. Traps that already cost time — do not rediscover these

1. **`ContDiff ℝ ⊤` is NOT smoothness.** In `WithTop ℕ∞` the top element is *analyticity*.
   A bump function is not analytic, so `ContDiff ℝ ⊤` on the packet domain is
   **unsatisfiable** and any witness against it is meaningless. Use `open scoped ContDiff`
   and write `∞`. Caught only by a type mismatch on `bump.contDiff`.
2. **Always diff a restated definition against its source before claiming you discharged it.**
   `WeilCompactSmoothGV1` / `WeilMomentConditionsV1` are restated in two modules because the
   source lives on another branch. Both were diffed byte-identical against
   `WeilCriterionCompactSmoothV1.lean` lines 34–40 on `proof/weil-analytic-v21-probe`.
   A drifted restatement discharges a lookalike statement, which is worth nothing.
3. **`Real.log` is even and `log 0 = 0`.** `fun x => φ (log x)` mirrors support onto the
   negative axis and hits `0`, so it is incompatible with `tsupport ⊆ Ioi 0`. The
   `if 0 < x` guard in `mulPacket` is load-bearing.
4. **Cross-branch import gap.** `WeilDiagonalConstantFromCothTailV1` imports
   `WeilArchimedeanCothTailV1` (this branch) **and** `WeilThreeBlockAnalyticConstantsV21`
   (`proof/weil-analytic-v21-probe` @ `c8021b22`, blob `92271bb5`). **No single branch in this
   repository builds it.** It was compiled against both trees side by side. Do not "fix" this by
   duplicating the file.
5. **Never background a script that itself backgrounds work.** A wrapper using `nohup … &`
   exits 0 immediately, the harness tracks the wrapper, the real job dies with the wrapper's
   shell, and you get a false green. Use the tool's own background flag on the real command.
6. **Axiom-free ≠ contentful.** `#print axioms` closure and theorem content are independent.
   Read every printed line; a clean closure on a vacuous theorem means nothing.

---

## 6. Operational constraints (non-negotiable)

- **Shell `git push` is blocked** by the AEGIS authority guard. Push via a GitHub content
  writer with an explicit non-main branch (`mcp__github__push_files`).
- **Never comment on a PR about Vercel `api-deployments-free-per-day` / deployment
  rate-limit failures.** Report them to the operator in chat. They recur on this repo.
- **Frozen constitutional files** — `sovereign-omega-v2/python/{gate.py,dna.py,router.py}`.
  Do not modify without `/guardian APPROVED`.
- `.claude.json` has an approved writer pinned by sha256 in
  `scripts/check-cognitive-writer-merge.py`. Never hand-author it.
- Do **not** open a PR for `proof/weil-analytic-v21-probe` (`c8021b22`) unless asked.
  Do not close or re-raise PR #509.
- After pushing, always sha256-verify the pushed blob against the bytes that compiled.

---

## 7. Repository health — read before creating anything

As of 2026-09-20:

| | |
|---|---|
| remote branches | **443** |
| merged into `main` | **20** |
| **not merged** | **422** |
| `proof/*` branches | 118, of which **0** are on `main` |
| open PRs | ≥100 (98 draft) |
| oldest branch | 84 days |

The repo's own `CLAUDE.md` says *"Nothing is 'done' until it is on `main`, verified. Stranded on
a feature branch = not done."* By that rule there are 422 unfinished things. **Do not add a new
branch for follow-up work on this lane — push to `proof/weil-arch-tail-order-lean-v1`.**

Also: `~/.claude/stop-hook-git-check.sh` used to raise false "N unpushed commits" alarms on a
diverged branch whose commits were already on `origin/main`. Fixed 2026-09-20 by replacing
`$upstream..HEAD` with `HEAD --not --remotes`. Backup at `…sh.bak`. If you see that alarm
again, check `git rev-list HEAD --not --remotes --count` before pushing anything.

---

## 8. Decisions waiting on the operator (do not act unilaterally)

1. **Branch cleanup.** 20 merged branches are safe to delete (zero commit loss). The 422
   unmerged need a triage report first — cluster by topic, separate unique content from
   superseded duplicates — then a human decides. **No bulk delete without explicit approval.**
2. **Direction of this lane.** Three options were put to the operator:
   - **A** — package the no-go results as a finished formalization library; stop the ladder.
   - **B** — attack `ANALYTIC_DIAGONAL_LOWER_V1` directly and fail fast.
   - **C** — continue step (iii). Not recommended; see §0.
   No option had been chosen when this handoff was written.

---

## 9. Related artifact worth copying from

`AEGIS_QuantumDNA_v1` (packaged 2026-09-07, local head `b0a84001`, status
`MACHINE_BOUND_EXACT_LOCAL_HEAD_ONLY`) is a better-executed piece of work than this lane and is
the template to imitate:

- it **anchors to something outside itself** — reproduces the documented Hawke2010 lifetime
  `775.5511022044088` fs to the last digit;
- it verifies against an **independent solver** (max deviation `9.265e-11`, bound `1e-7`);
- its first run was **rejected** on negative eigenvalues, and the fix was to tighten the
  integrator, **not** to loosen the acceptance threshold;
- it states its boundaries as theorems about scope: figure reproduction *not* claimed, no
  p-values on deterministic traces, 1 and 3 eV marked numerical controls not physiology,
  `HYPOTHESIS_NOT_EXPERIMENTALLY_TESTED`.

The Lean lane has (2) and (4) but not (1) — no result here is checked against anything outside
the repository. That is the single biggest weakness of this lane.

Note it is also **local-head-only** — never admitted remotely. Same disease as the 443 branches.

---

## 10. Abjad profile transport — a settled contract (different domain, one shared principle)

Not part of the Weil lane. Recorded here because it shares exactly one principle with §4
and because the contract is closed on both sides, which is rare enough to write down.

Domain: the archival Abjad encoder and its two letter-value profiles (Mashriqi, Maghribi),
evaluated in F101 at t = 2. Source package: `aegis-archive-voynich-link` (local, not in this
repository). Composition of adjacent letters is Horner:

    single letter with value v   →   (v, t)
    concatenation                →   e_AB = e_A + u_A · e_B ,   u_AB = u_A · u_B

### The question

Is the compressed state `(e, u)` enough to compute the other profile's evaluation?

### Witness 1 — the pair `(e_M, u)` is NOT sufficient

    ا س : [1,60] → e = 1 + 2·60 = 121 ≡ 20 (mod 101),  u = 4   →  (20, 4)
    ب ط : [2,9]  → e = 2 + 2·9  = 20,                  u = 4   →  (20, 4)

Same state, same length — but the required Maghribi evaluations are 96 and 20 respectively.
So no function of `(e_M, u)` alone performs the profile change. This is an impossibility
result and it stays true; nothing below overturns it.

### Witness 2 — the triple `(e_M, e_G, u)` IS sufficient for both evaluations

    S_A ⋆ S_B = ( e_{M,A} + u_A·e_{M,B} ,  e_{G,A} + u_A·e_{G,B} ,  u_A·u_B )   (mod 101)

Associative — both bracketings give `e_A + u_A e_B + u_A u_B e_C` and `u_A u_B u_C`.
Two-sided identity `(0, 0, 1)`.

The fix does not defeat Witness 1, it **avoids** it: carry both evaluations through the same
`u` and the profile change stops being a recovery problem. Reading a profile is still a
function — the projection `π₂(e_M, e_G, u) = e_G`. The difference is that this one exists.

Cost: **O(1) state, O(1) merge of two summaries, O(n) initial scan of the sequence.**
The scan is unavoidable; only the state and the merge are constant.

### Witness 3 — the triple is NOT sufficient to reconstruct the sequence

    [1,2] → (5, 5, 4)
    [3,1] → (5, 5, 4)

Length 2, and exhaustive search over letter values 1–28 confirms **2 is the minimal collision
length** — this pair is the first one found. (Values 1, 2, 3 coincide in both profiles, so the
witness needs no profile asymmetry.)

A separate, unbounded family: since `ord(2) mod 101 = 100`, for every letter `a` and every
`k ≥ 0`,

    S(a^{100k}) = (0, 0, 1)

so the fibre over the identity is **infinite** — it contains the empty word and arbitrarily
long repetitions of every letter. Note `n = 100` is minimal for reaching *the identity*
(it needs `u = 2ⁿ = 1`, hence `100 | n`); it is **not** the minimal collision length, which is 2.

### The contract

- Carry the triple for computing through profiles and for composition.
- Keep a separate record that preserves content when letters must be reconstructed.

The triple preserves the required evaluations and their composition; content is preserved
separately. Full Field101 retains coefficients (O(n)) and is what the existing reconstruction
procedure needs — it is not made redundant by the triple, and the triple is not made redundant
by it. They answer different questions.

### Shared principle with §4

A function factors through a projection **iff** it is constant on the projection's fibres.
`no_abjad_function_gives_vonMangoldt` is a witness of non-constancy on one fibre of `n mod 36`
(`5` and `41` are both prime, share every abjad output, `log 5 ≠ log 41`). Witness 1 and
Witness 3 above are the same shape on different projections. This is a shared principle only —
it does **not** identify the different Abjad definitions with each other, and the fibres are
different objects (`n mod 36` there, the F101 summary here).

### Separation of what is established

| | |
|---|---|
| **Mathematical result** | Witnesses 1–3 and the associativity/identity of `⋆`. Elementary, checkable by hand. |
| **Executed tests** | Re-derived independently in this session in Python: the three witnesses, associativity on 200k random triples plus the algebraic argument, the identity element, `ord(2) = 100`, exhaustive minimal-collision search over values 1–28, and the infinite fibre for `k = 1,2,3`. The source package's own `SHA256SUMS.txt` verifies 125/125. |
| **Integration** | **None.** Nothing here is in this repository, nothing is on `main`, no Lean or Coq kernel attestation exists for any of it, and the source package states it made no remote changes or merges. |

These three are separately verifiable and must not be conflated. The mathematics being closed
says nothing about whether it is integrated, and it is not.

---

## 11. CORRECTION — this handoff was written from a 14-module view

Added 2026-09-20, after the sections above. **Read this before trusting §0-§4.**

Sections 0-4 were written while looking only at `proof/weil-arch-tail-order-lean-v1`.
They report 14 modules and 138 theorems and present a status table for the whole
chain. That framing is wrong. The repository actually carries:

| | |
|---|---:|
| Lean modules under `formal/bridges/lean/` across all branches | **103** |
| theorems + lemmas in them | **608** |
| branches carrying them | **80** |
| modules with explicit `*_OPEN` markers | **35** |
| distinct declared-open obligations | **45** |

Specifically, §3 said autocorrelation (step iii) was untouched. It is not.
`WeilAutocorrelationRealityV1`, `WeilAutocorrelationClosureV1`,
`WeilAutocorrelationPrimeWindowsV1`, `WeilAutocorrelationPoleAggregationV1` and
`WeilAutocorrelationPrimeNormalFormV1` exist on other branches, and
`WeilArchimedeanConvergenceV1` already proves the archimedean integral converges
on the compact-smooth domain. §3's row for "autocorrelation vanishing outside the
log-support" remains accurate as a statement, but the surrounding claim that the
area was untouched was false.

### What the repository itself declares open

These are `*_OPEN` markers written into module headers by their authors, counted
across all branches. This is the repository's own accounting, not mine:

| obligation | modules declaring it |
|---|---:|
| `RH_EQUIVALENCE_OPEN` | 29 |
| `EXPLICIT_FORMULA_OPEN` | 16 |
| `CRITICAL_LINE_RE_HALF_OPEN` | 14 |
| `EXPLICIT_FORMULA_THEOREM_OPEN` | 9 |
| `HEIGHT_LIMIT_EXISTENCE_OPEN` | 6 |
| `FULL_CRITICAL_STRIP_OPEN` | 5 |
| `EXPLICIT_FORMULA_IDENTITY_OPEN` | 5 |
| `LOWER_ZERO_LOCALIZATION_OPEN` | 4 |
| `HEIGHT_TRUNCATION_EQUIVALENCE_OPEN` | 4 |
| `GLOBAL_ZERO_SUM_CONVERGENCE_OPEN` | 4 |
| `CONDITIONAL_SYMMETRIC_CONVERGENCE_OPEN` | 4 |
| `ZERO_SUM_CONVERGENCE_OPEN` | 3 |
| `ZERO_COUNTING_BOUND_OPEN` | 3 |
| `WEIL_CLASS_SHELL_MASS_SUMMABILITY_OPEN` | 3 |
| `MELLIN_DECAY_ESTIMATE_OPEN` | 2 |
| `GLOBAL_ZERO_SUM_OPEN` | 2 |
| `GLOBAL_WEIL_SIGN_OPEN` | 2 |
| `FULL_WEIL_CLASS_COVERAGE_OPEN` | 2 |
| `ARITHMETIC_NEGATIVITY_OPEN` | 2 |
| `ACTUAL_QUADRATIC_SHELL_BOUND_OPEN` | 2 |

`RH_EQUIVALENCE_OPEN` appears in 29 modules. The repository does not claim RH
anywhere, and says so 29 separate times.

### Module families

- `Weil*` — 26
- `Zero*` — 14
- `WeilThreeBlock*` — 10
- `WeilArch*` — 8
- `ZeroHeight*` — 7
- `WeilWidth*` — 5
- `WeilFixedLine*` — 5
- `WeilAutocorrelation*` — 5
- `WeilDiagonal*` — 4
- `ZetaDivisor*` — 3
- `WeilPairedHadamard*` — 3
- `Aegis*` — 3
- `ZeroShell*` — 2
- `Abjad*` — 2

### What this correction does NOT establish

- I have **not** read all 103 module headers, only the inventory metadata.
- I have **not** compiled any module outside the 14 on this lane. Presence of a
  file is not evidence that it builds, and the `*_OPEN` markers are author
  declarations, not kernel facts.
- The theorem count is `grep -cE '^(theorem|lemma) '`, so it counts declarations,
  not distinct results; the same lemma restated on two branches counts twice.
- Branch attribution picks one branch per module name; a module present on several
  branches may differ between them and was **not** diffed.

**Treat §0-§4 as a report on one lane, and this section as the only statement here
about the repository as a whole.**
