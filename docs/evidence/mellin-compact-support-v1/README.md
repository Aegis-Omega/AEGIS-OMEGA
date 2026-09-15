# `mellinConvergent_of_hasCompactSupport` — Mathlib upstream candidate, kernel-checked

This directory preserves the exact source, patch, and verification logs for a single Lean 4 lemma
drafted for upstream submission to `Mathlib/Analysis/MellinTransform.lean`. It records what was
mechanically verified against a pinned Mathlib revision and separates that from what has **not**
been established (upstream acceptance, any claim about the Riemann Hypothesis).

## Identity

- **Lemma:** `mellinConvergent_of_hasCompactSupport`
- **Statement:** if `f : ℝ → E` is continuous with compact support and `tsupport f ⊆ Ioi 0`, then
  `MellinConvergent f s` for every `s : ℂ` (`E` any complex normed space).
- **Target file:** `Mathlib/Analysis/MellinTransform.lean`, section `MellinConvergent`, inserted
  immediately after `mellin_convergent_iff_norm`.
- **Mathlib revision pinned:** `78f7ceb75eb8545d8f24744941f3629c16eb7040`
- **Pristine target file SHA-256 at that revision:**
  `81851086004a6e5424da555061a4b2f9d2e7cece148d9d49c3537a05adba73ff`
- **Target file SHA-256 with the patch applied:**
  `216d04d4eba956b298f8106e4114b61e5e0b08cf57da13b95f4009f76b517fb0`
- **Toolchain:** Lean `4.34.0` (commit `293d5d0c`), identical to Mathlib's `lean-toolchain` at the
  pinned revision. Toolchain obtained from the official release tarball because `elan` could not
  resolve its self-update endpoint in this environment.
- **Patch:** one file, `+25` lines, zero existing lines modified.

## Gap this fills

At the pinned revision, `Mathlib/Analysis/MellinTransform.lean` proves `MellinConvergent` only from
`isBigO` decay hypotheses (`mellin_convergent_of_isBigO_scalar`, `mellinConvergent_of_isBigO_rpow`,
…). No lemma derives convergence from compact support. Name-collision check across `Mathlib/`
returned no other occurrence of `mellinConvergent_of_hasCompactSupport`. The name follows the
neighbouring `mellinConvergent_of_isBigO_rpow`.

## Verification lanes (each recorded distinctly, not collapsed into one PASS)

| Lane | Command | Result | Log |
|---|---|---|---|
| `mathlib_kernel_compile` | `lake env lean MellinCompactSupport.lean` against **pristine** Mathlib, mirroring the target file's `open` context | exit 0, no warnings | `logs/01-standalone-compile.log` |
| `axiom_audit` | `#print axioms mellinConvergent_of_hasCompactSupport` | `[propext, Classical.choice, Quot.sound]` — no `sorryAx` | `logs/02-axioms.log` |
| `mathlib_module_build_with_lemma_inserted` | patch applied, `lake build Mathlib.Analysis.MellinTransform` with `linter.mathlibStandardSet` active via the lakefile | 2794/2794 jobs, exit 0 | `logs/03-lake-build-inserted.log` |
| `mathlib_env_linter` | `lake exe runLinter Mathlib.Analysis.MellinTransform` (15 linters, 141 917 declarations) | `Linting passed`, exit 0 | `logs/04-runLinter.log` |
| `mathlib_env_linter_negative_control` | same, after appending a deliberately defective declaration | correctly **rejected** (`synTaut` + `unusedArguments`, exit 1) — proves the lane bites | `logs/05-runLinter-negative-control.log` |
| `non_vacuity_witness` | `MellinCompactSupport_NonVacuity.lean`: continuous tent `t ↦ max 0 (1 − |t − 2|)` on `Icc 1 3`, `witness 2 ≠ 0`, all three hypotheses discharged and the lemma applied | exit 0 | `logs/06-nonvacuity-witness.log` |
| `mathlib_text_style_linter` | `lake exe lint-style Mathlib.Analysis.MellinTransform` | exit 0, **but no negative control fired** — recorded as `UNVERIFIED`, not `PASS` | — |

Phase A (lanes 1–2) ran against the pristine module; phase B (lanes 3–6) against the module with
the patch applied. The `#print axioms` output was produced with the lemma defined only in the
scratch file, so it is the lemma's own dependency set, not inherited from a prior build.

## Hash-pinned artifacts

| Artifact | Role | SHA-256 |
|---|---|---|
| `mellinConvergent_of_hasCompactSupport.patch` | the upstream diff | `c1da13bba9c7e0c91c0906a3a0a11128edca6f597032f1e9357fd6fe7e022e69` |
| `MellinCompactSupport.lean` | exact standalone file compiled in lane 1 | `05569f883117e90e75c2ecc842761876daa70b214b43e9f015aa0514bb0d48d1` |
| `MellinCompactSupport_AxiomCheck.lean` | lane 2 input | `ef74d7fa94b4cf08f029544664594bd4d85ea29e143bd4762396750476965498` |
| `MellinCompactSupport_NonVacuity.lean` | lane 6 input | `6946437b9662aa78ac55a1e092fdbf40fa7d6a5042e9a86d0071983257c4ff69` |

`SHA256SUMS` in this directory covers every file, logs included.

## Findings recorded during verification

1. The first compile of the reviewed draft **failed**: `continuousAt_ofReal_cpow_const` lives in
   `namespace Complex` and is only unqualified inside the target file because of its
   `open Complex hiding exp log`. Two independent source-level reviews had marked the draft
   `SOURCE_VERIFIED` without catching this. The scratch file now mirrors the target file's `open`
   lines exactly; the patch itself is unchanged and correct in situ.
2. `hfs.smul_left` elaborated without the explicit `(f := …)` fallback.
3. A first `lint-style` invocation with a file path silently linted nothing (it takes module names).
   Caught by negative control; hence the `UNVERIFIED` row above rather than a claimed PASS.

## What this does NOT establish

- **`upstream_submission: NOT_SUBMITTED`.** No pull request has been opened against
  `leanprover-community/mathlib4`. Mathlib CI, review, and naming/placement decisions by maintainers
  have not occurred.
- **`authority_effect: NONE`.** This is a general-purpose analysis lemma. It changes the epistemic
  status of nothing in AEGIS beyond itself.
- **`RH: NOT_PROVEN`.** The lemma is a convergence statement for compactly supported test
  functions. It is not evidence for or against the Riemann Hypothesis, any Weil-positivity claim,
  or any `RH_CORRESPONDENCE_OBLIGATION_DAG_V1` node.
- Verification was performed on a single Linux x86_64 host. No CI lane in this repository
  re-executes it; re-verification requires the pinned Mathlib revision plus its cached oleans
  (`lake exe cache get Mathlib.Analysis.MellinTransform`).
