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
