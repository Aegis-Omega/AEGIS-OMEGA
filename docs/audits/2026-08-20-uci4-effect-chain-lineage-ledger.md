# AEGIS Ω UCI-4 Effect-Chain Lineage Ledger

Date: 2026-08-20
Status: IMPLEMENTED / EXTERNAL EXACT-HEAD COMPONENT WITNESS ESTABLISHED / FINAL PR-HEAD RECHECK PENDING
Authority: EVIDENCE_ONLY

## 1. Exact lineage

```text
CANONICAL_MAIN = 32b7eb6a37fb69d19dd80189390b6641c5004ef1
UCI4_PARENT = ebec2f9c8fa00f54605d859df61512108ff3b71d   # PR #275 exact checkpoint
SOURCE_EFFECT_LINEAGE = #268 -> #270 -> #272 -> #273
SOURCE_EFFECT_LINEAGE_TIP = 6407db1b0c4176f67a1d7ecbb16eca77d131d87e
UCI4_RED_CANDIDATE = 13a8ffbc907fc91751f84092b7befbbad47dd0f6
UCI4_FIRST_GREEN_RUNTIME_CANDIDATE = 1cdd2c6331fcd2c18d75baf2c60b914dd30f4548
```

UCI-4 was created as a narrow successor of the UCI spine. The frozen effect-verification source files were transplanted by Git blob identity rather than by merging the historical stacked branches.

## 2. Preserved semantic chain

```text
TransitionIdentity
  -> DecisionReceipt
  -> ExecutionReceipt
  -> independent EffectWitness / EffectEvidence
  -> EffectVerificationResult
  -> verifier-gated EffectReceipt
  -> CompleteVerificationResult
```

Mandatory boundaries remain:

```text
DecisionReceipt != ExecutionReceipt != EffectReceipt
DEFER -> WAITING
DEFER -/-> EXECUTE
ExecutionReceipt -/-> EffectReceipt
CompleteVerificationResult -/-> AdmissionRecord
```

Only `PERMIT` satisfies decision authority. Effect evidence originates from an independently bound observation adapter. No generic `EffectReceipt` producer exists. `CompleteVerificationResult=TRUE` remains verifier output only.

## 3. TDD RED witness

The preregistered UCI-4 integration test was committed before the production SDK surface.

A first external witness attempt was invalid as RED evidence because the runner lacked `pytest` and the initial shell harness did not fail closed after capturing the command exit code. That result was rejected rather than promoted.

The corrected independent witness used `pytest==8.3.5` and checked out the exact candidate:

```text
RUNNER_REPOSITORY = tarikskalic33/info
RUN_ID = 32347655528
JOB_ID = 96359724715
CANDIDATE_SHA = 13a8ffbc907fc91751f84092b7befbbad47dd0f6
EXPECTED_PARENT_SHA = ebec2f9c8fa00f54605d859df61512108ff3b71d
EXACT_LINEAGE = PASS
```

Observed intended RED failure:

```text
ModuleNotFoundError: No module named 'harness.sdk.transition_receipts'
UCI4_RED_INTENDED_MISSING_TRANSITION_RECEIPTS = PASS
```

## 4. GREEN implementation witness

The production transplant commit reused the exact tested Git blobs from the frozen #273 proofline for the transition/effect runtime, schemas, authority producers, and PR1→PR4 falsification suites.

Independent hosted execution then checked out exact candidate:

```text
RUNNER_REPOSITORY = tarikskalic33/info
RUN_ID = 32348141772
JOB_ID = 96361208538
CANDIDATE_SHA = 1cdd2c6331fcd2c18d75baf2c60b914dd30f4548
UCI_PARENT_SHA = ebec2f9c8fa00f54605d859df61512108ff3b71d
FROZEN_SOURCE_TIP = 6407db1b0c4176f67a1d7ecbb16eca77d131d87e
EXACT_LINEAGE = PASS
```

Observed:

```text
UCI4_SCHEMA_VALIDATION = 6/6 PASS
PR1_TO_PR4_PLUS_UCI4_TESTS = 79/79 PASS
FAILURES = 0
```

The executed set was:

- `test_transition_receipts_pr1.py`
- `test_transition_receipts_cli_pr1.py`
- `test_effect_adapters_pr2.py`
- `test_effect_verifier_pr3.py`
- `test_complete_verifier_pr4.py`
- `test_complete_verifier_pr4_receipt_binding.py`
- `test_uci4_effect_chain_integration.py`

This establishes an external exact-head component witness for the first GREEN runtime candidate. It is not AEGIS repo-native CI and does not establish admission.

## 5. Scope and contamination check

Relative to `#275@ebec2f9c...`, the UCI-4 slice is limited to:

- transition/effect SDK modules;
- canonical authority client/CLI receipt emission;
- six closed schemas;
- frozen PR1→PR4 falsification tests;
- one UCI integration test;
- dedicated UCI-4 workflow;
- implementation/audit documentation;
- repository-generated `.claude.json` provenance refresh.

No provider-organism, memory, UI, cloud deployment, billing, domain capability, or AtomicAdmission implementation is included.

## 6. Explicit non-claims

```text
ATOMIC_ADMISSION = NOT_IMPLEMENTED
EFFECT_BOUND_ADMISSION = UNAVAILABLE
CAUSAL_CLAIM_ADMISSION = NOT_IMPLEMENTED
PRODUCTION_ADMISSION = NOT_ESTABLISHED
DISTRIBUTED_LINEARIZABILITY = NOT_ESTABLISHED
PRODUCTION_ROBUSTNESS = NOT_ESTABLISHED
AGI = NOT_ESTABLISHED
```

Provider/model output remains evidence only, never authority. D3 remains explicitly operator-approval-bound. D4 remains denied absent separately admitted policy.

## 7. Next gate

The final PR head after CI/ledger-only changes requires a fresh exact-head witness. No earlier GREEN run may be presented as PASS for a later SHA. UCI-5 AtomicAdmission remains a separate successor and must not be folded into this proofline by assertion.
