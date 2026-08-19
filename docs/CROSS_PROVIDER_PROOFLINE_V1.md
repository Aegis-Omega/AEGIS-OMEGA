# AEGIS Ω Cross-Provider Proofline v1

Status: IMPLEMENTATION CONTRACT / NO AGI CLAIM
Parent: `feat/frontier-provider-mesh-v1@31aec51c32caa2431cb94ee742c912059802568b`

## Objective

Evaluate heterogeneous model/provider agents under one provider-neutral, evidence-bound execution contract. Provider output is evidence, never authority. The benchmark is designed to test the hypothesis that a verified collective can outperform individual agents under equal constraints; it does not presuppose or certify AGI.

## Compared execution classes

1. `SINGLE_AGENT` — one provider/model completes the work order.
2. `PROVIDER_TEAM` — multiple workers from one provider cooperate under the same aggregate budget.
3. `AEGIS_VERIFIED_COLLECTIVE` — heterogeneous workers cooperate through typed handoffs while AEGIS retains authority and verification.

All classes receive the same task specification, initial state commitment, allowed tool/capability envelope, wall-clock ceiling, token/cost ceiling, consequence class, and verifier policy.

## Proofline

```text
TaskEnvelope
  -> CandidateAssignment
  -> DecisionReceipt
  -> ExecutionReceipt
  -> WorldObservation
  -> EffectEvidence
  -> VerifyEffect
  -> EffectReceipt
  -> TaskVerification
  -> ScoreRecord
```

No arrow is an equivalence. In particular:

```text
DecisionReceipt != ExecutionReceipt != EffectReceipt
ExecutionSuccess != EffectSuccess
ProviderConfidence != Verification
Score != Authority
```

Until the EffectBoundClosure implementation lane supplies a valid verifier-gated EffectReceipt, any task requiring an external effect MUST finish `NOT_ADMITTED`. There is no legacy receipt fallback.

## Provider-neutral task envelope

Each task MUST bind at least:

- `task_id`
- exact benchmark/version digest
- exact source/repository SHA when code is involved
- initial state commitment
- hidden evaluation seed commitment
- allowed capabilities/tools/network domains
- consequence class
- token ceiling
- monetary ceiling
- wall-clock ceiling
- maximum delegation depth
- verifier-policy commitment
- admission-policy commitment
- nonce/fence where authoritative mutable state is involved

Provider-specific metadata may be recorded for provenance but MUST NOT change the scoring contract.

## Evaluation dimensions

Scores are reported as a vector, not collapsed into an AGI label:

- `competence`: task-correctness against deterministic or externally grounded criteria
- `generalization`: performance on held-out/novel task families
- `reliability`: successful verified runs / eligible runs, with confidence intervals
- `evidence_integrity`: completeness and validity of required witness material
- `authority_compliance`: absence of capability, delegation, budget, state, or admission violations
- `efficiency`: verified utility normalized by declared cost/tokens/time
- `recovery`: ability to detect, contain and recover from failed workers without invalid admission
- `collective_gain`: verified collective performance relative to the strongest eligible single-agent baseline under matched resources

Raw per-task results MUST remain available. Aggregate ranking MUST declare weighting/versioning explicitly.

## Hard gates

A candidate is `NOT_ADMITTED` for the task when any required obligation is FALSE, UNKNOWN, ERROR, MISSING, stale, or incompatible. Hard-gate failures include:

- fabricated or unverifiable evidence;
- authorization/capability violation;
- budget or consequence-class violation;
- stale state, nonce, epoch, lease, or fence;
- receipt splicing across transition identities;
- missing required effect evidence;
- verifier-policy mismatch/downgrade;
- current revocation or admission-policy rejection;
- benchmark leakage proven by the evaluation harness.

A high competence score never overrides a hard-gate failure.

## Anti-gaming and independence

- Hidden tasks/seeds are committed before execution and revealed only for verification.
- Workers cannot edit verifier policy, benchmark ground truth, score weights, or admission policy.
- Authorization-derived artifacts are never acceptable evidence for `V_effect`.
- Provider/model self-reported confidence is telemetry only.
- The evaluator records provider/model/version, tool calls, cost, latency, receipts, observations, verifier result, and exact code/config digests.
- Same-model replicas are not assumed independent; correlated failure is measured rather than multiplied away.

## Initial task families

The harness should grow through versioned task packs covering:

1. repository reasoning and exact-SHA code repair;
2. research claims requiring external evidence;
3. tool-use planning under capability constraints;
4. long-horizon stateful execution and recovery;
5. cross-domain transfer on held-out tasks;
6. adversarial authority/replay/splicing attempts;
7. external-effect tasks once EffectBoundClosure is executable.

## Collective-gain hypothesis

For matched task set `T` and resource envelope `B`:

```text
H_collective:
VerifiedUtility(AEGIS_VERIFIED_COLLECTIVE, T, B)
  > max_i VerifiedUtility(SINGLE_AGENT_i, T, B)
```

This is a falsifiable hypothesis. A failed or null result is retained as evidence; the harness MUST NOT tune away unfavorable providers/tasks after observing results.

## Promotion boundary

The words `AGI`, `general intelligence`, or `superintelligence` are not benchmark outcomes by default. Promotion requires a separately versioned claim protocol specifying breadth, novelty, transfer, autonomy, reliability, resource controls, statistical thresholds, and independent reproduction.

The immediate implementation target is narrower and testable:

> Can a provider-neutral AEGIS collective produce more verified utility than the strongest individual agent under matched resources without relaxing evidence or authority constraints?

## Required implementation slices

- canonical schemas for TaskEnvelope, CandidateRun, ScoreRecord and BenchmarkManifest;
- deterministic scorer with versioned weights and hard gates;
- provider adapter normalization over the existing frontier mesh;
- hidden-seed commitment/reveal protocol;
- replayable run manifest binding exact code/config/provider versions;
- task packs and falsification tests;
- public leaderboard generated only from admitted ScoreRecords.

No provider is granted authority by winning, and no leaderboard result modifies canonical AEGIS state.