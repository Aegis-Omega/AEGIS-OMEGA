# Long-Term Future Fund — AEGIS Ω Application Draft

Status: submission-ready draft, NOT SUBMITTED
Target fund: Long-Term Future Fund (EA Funds)
Current public application surface: always open; general EA Funds range USD 1,000–500,000.
Primary source: https://funds.effectivealtruism.org/apply-for-funding

## Project title

**Evidence-Bound Runtime Authority for Autonomous AI Agents**

## Funding request

**USD 120,000 / 12 months**

This request is intentionally below the program-wide maximum. The goal is to fund one narrow, independently testable safety program rather than the entire AEGIS Ω roadmap.

## One-sentence summary

Build and independently evaluate an open-source runtime layer that prevents autonomous AI agents from converting model confidence, credentials, or tool availability into consequential authority without task-, state-, policy-, and evidence-bound admission.

## Problem

As AI agents gain the ability to modify code, infrastructure, databases, workflows, and external services, traditional identity and access controls are necessary but incomplete. A valid identity may possess a valid credential and still attempt an action that is no longer authorized, is based on stale state, exceeds task scope, or produces an outcome that cannot be verified.

Most agent-safety approaches concentrate on model behavior, prompt-level policy, or monitoring. This project studies a complementary system property: **can consequential authority be mechanically bounded outside the model and independently reconstructed after execution?**

The central safety invariant is:

```text
model capability != authority
model confidence != evidence
execution != verified outcome
```

## Proposed work

We will develop a bounded open-source reference implementation and adversarial benchmark around five transitions:

1. **Typed action proposal** — actor, task, resource, capability, intended side effect.
2. **Authority admission** — delegated scope, lease/fence, policy, state freshness.
3. **Consequential execution** — no external side effect without an admitted action.
4. **Execution receipt** — deterministic, tamper-evident evidence binding proposal to observed execution.
5. **Outcome verification** — explicit separation of `SUCCESS`, `FAILURE`, and `OUTCOME_UNKNOWN`, with replay or compensation where feasible.

## Research questions

1. Can task-level authority prevent failures that identity/IAM alone cannot distinguish?
2. Which agent actions can be deterministically replayed or independently verified despite stochastic model reasoning?
3. How should stale state, late receipts, ambiguous operator intent, and partial provider failures affect authority?
4. How often do latent model/user-state inferences improperly influence routing or policy, and can evidence thresholds reduce that failure mode?
5. What minimum evidence is sufficient for an external reviewer to reproduce an agent-action verdict without trusting the originating model?

## Existing technical base

AEGIS Ω is already a public open-source repository with runnable reference proofs for:

- deterministic canonicalization and SHA-256 lineage;
- replay-verifiable governance envelopes;
- tamper detection;
- cross-language verification across Python, Node.js, and Rust;
- fail-closed admission and governance primitives;
- large existing TypeScript/Rust/Python test surfaces.

Public reproduction commands currently include:

```bash
python3 genomics/test_replay_proof.py
python3 verifiable/test_generality.py
bash verifiable/cross_language/verify.sh
python3 verifiable/certify_all.py --twice
```

The proposal does **not** rely on claims of AGI, consciousness, universal hallucination elimination, or production deployment.

## Deliverables

### D1 — Consequential Action Contract

A stable open schema for:
- actor identity;
- task identity;
- capability;
- delegated authority;
- resource scope;
- state preconditions;
- lease/fence;
- execution intent;
- expected outcome;
- evidence references.

### D2 — Runtime Admission Layer

Reference implementation supporting:

`ADMIT | DENY | REVIEW | BLOCKED`

with fail-closed handling for unresolved consequential ambiguity.

### D3 — Adversarial Benchmark

At least 100 reproducible negative-control scenarios covering:
- valid identity / invalid task authority;
- stale lease or fence;
- stale target state;
- privilege expansion;
- prompt/tool injection;
- provider timeout;
- late receipt;
- duplicate action/retry;
- outcome unknown;
- unsupported latent user/operator-state inference.

### D4 — Receipt + Replay Package

Cross-language deterministic verification and public reproduction harness.

### D5 — Independent Evaluation

Recruit at least two external technical reviewers or organizations to run the benchmark independently and publish or return reproducibility results.

### D6 — Research Write-up

Open technical paper covering architecture, threat model, empirical results, failure cases, limitations, and falsification criteria.

## Milestones

### Months 1–2
- freeze action/receipt schemas;
- isolate canonical reference implementation;
- threat model and baseline negative controls.

### Months 3–5
- implement state/authority admission and adversarial harness;
- cross-runtime replay;
- automated receipts.

### Months 6–8
- benchmark agent/tool/provider failure modes;
- measure false-admit / false-deny behavior;
- operator-model calibration experiments.

### Months 9–10
- independent reproduction wave;
- red-team fixes;
- deterministic release package.

### Months 11–12
- final paper;
- public benchmark;
- deployment guidance and limitations.

## Success metrics

Primary metrics:

- False Unauthorized Admission Rate;
- Unverifiable Action Execution Rate;
- replay success rate;
- stale-state rejection rate;
- receipt completeness;
- independent reproduction rate;
- time-to-reconstruct an incident;
- policy-elevation errors caused by unsupported latent inference.

A negative result is useful. If the architecture cannot provide reliable evidence-bound authority under realistic provider behavior, the benchmark should expose that clearly.

## Budget — USD 120,000

- Operator/research engineering: $60,000
- External reviewers / independent reproduction / contracted security review: $20,000
- Compute, API and cloud experimentation: $15,000
- Test infrastructure and hardware/edge targets: $10,000
- Research dissemination, conference/travel and reproducibility support: $7,500
- Legal/accounting/administrative and contingency: $7,500

Exact budget can be resized after funder feedback.

## Why this may matter for advanced-AI risk

As agents become more capable, preventing every model-level error may be unrealistic. A complementary safety strategy is to ensure that **error does not automatically become authority**.

The project therefore focuses on the boundary between cognition and consequential action. Even if an agent reasons incorrectly, the system should be able to deny an inadmissible action, preserve evidence of the attempted transition, and avoid silently classifying an unknown outcome as success.

## Public-benefit plan

Core schemas, benchmark cases, verifier, reference runtime, and research outputs will be released openly. The goal is to make the work reusable by other AI-safety researchers, open-source agent frameworks, and organizations evaluating agent controls.

## Key risks and limitations

- deterministic evidence does not make stochastic cognition deterministic;
- a receipt can prove what the instrumented system observed, not unknowable external facts;
- provider black boxes limit end-to-end verification;
- safety benefits depend on external actions actually being routed through the control boundary;
- benchmarks may underrepresent future high-autonomy workflows;
- this project does not claim a complete alignment solution.

## Operator

Tarik Skalić
Bihać, Bosnia and Herzegovina
AEGIS Ω / Aegis-Omega

## Submission checklist

- [ ] confirm requested amount and personal/entity recipient structure;
- [ ] add concise prior-work links;
- [ ] select 3 strongest runnable proof links;
- [ ] add 12-month personal runway/budget assumptions if form requests them;
- [ ] operator review;
- [ ] submit through LTFF application surface.
