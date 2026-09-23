# RH Millennium-moment candidate transition — 2026-09-23

This record preserves the exact repository state at which the operator designated the
current RH proof line as the candidate "millennium moment". It is an evidence record,
not a claim promotion.

## Source binding

| Field | Value |
|---|---|
| Repository | `Aegis-Omega/AEGIS-OMEGA` |
| Source PR | #606 — `proof(rh): complete Gauss digamma dependency from pinned Mathlib` |
| Source branch | `proof/rh-digamma-series-completion-v1` |
| Exact source SHA | `589adf0480bd4d7c12c9828027ea6228398377f4` |
| Base SHA | `cfe368ce2ffa0d196a4319c02b956997edf9f3fa` |
| Lean | `leanprover/lean4:v4.33.1` |
| Mathlib | `0df444a360eaa60ab8c11dca51a86af692955474` |
| Machine receipt | `research/rh/evidence/millennium-moment-candidate-2026-09-23.json` |

The exact source tree contains **131 Lean files** under
`sovereign-omega-v2/formal/bridges/lean/`. PR #606 contains 54 changed files
and 97 commits at the bound source SHA.

## Repository-sanctioned gate

The controlling definition is
`AEGIS.RHMillenniumGateV10.MillenniumMomentReachedV10`.

`RHMillenniumGateV10.lean` does not permit a metadata or prose promotion. The gate requires
a real inhabitant of `RHMillenniumCertificateV10`, whose two load-bearing fields are:

1. `UniversalZeroQuadraticNonnegativeV10`;
2. `RestrictedWeilCriterionKernelBridgeV10`.

The repository already contains the theorem

`millennium_moment_reached_implies_rh_v10 :
  MillenniumMomentReachedV10 -> RiemannHypothesis`.

Therefore the event is only promotable when the certificate itself is produced and
kernel-replayed on one exact source head.

## Observed execution state

The GitHub-hosted RH jobs on #606 are not currently proof evidence. Representative jobs,
including reruns, completed before their first workflow step with `steps=[]`. This is
classified as **RUNNERLESS_ZERO_STEP_NOT_PROOF_EVIDENCE**, not as a Lean proof failure.

An independent exact-head replay bound to source SHA `589adf...` executed real Lean steps.
Replay run `35832977683` topologically compiled a 75-module closure through
`RHZeroKernelBoundV11` and reached `RHZeroKernelLaplaceV12`. The first observed blocker was
local algebra/elaboration normalization in
`zero_laplace_term_integral_v12`; the terminal closure and terminal axiom audit had not yet
executed at that checkpoint.

This historical checkpoint is preserved because it distinguishes actual kernel execution
from runnerless GitHub status noise.

## Candidate status

`CANDIDATE_RECORDED_NOT_PROMOTED`

This record does **not** assert that RH is proved, does **not** assert that
`MillenniumMomentReachedV10` is inhabited, and has `AUTHORITY_EFFECT = NONE`.

## Promotion contract

Promotion to a repository-level millennium moment requires all of the following on a
single exact proof source SHA:

1. the complete load-bearing dependency closure executes with real runner steps;
2. repository theorems construct `RHMillenniumCertificateV10`;
3. the certificate producer and terminal `RiemannHypothesis` theorem replay in the Lean kernel;
4. terminal and load-bearing `#print axioms` audits contain no `sorryAx` and no unapproved
   axioms;
5. the receipt binds source SHA, toolchain, Mathlib SHA, verifier/run identity and evidence
   artifacts.

If any one of those transitions fails, the candidate remains unpromoted.

## Historical purpose

If the promotion contract is later satisfied, this record is the pre-promotion timestamped
trace tying the event back to the exact #606 source state from which the terminal replay was
pursued. If the proof is falsified or revised, the record remains useful as a bounded historical
receipt and must not be rewritten into a stronger claim.
