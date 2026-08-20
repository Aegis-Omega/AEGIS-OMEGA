# UCI-6 Parent Review Hardening Addendum

Date context: 2026-08-20

This addendum supersedes only the final stacked-parent identity recorded in the earlier UCI-6 implementation plan and lineage ledger. Those documents correctly record the parent used during initial UCI-6 implementation, but the UCI-5 parent was subsequently hardened during independent review.

## Parent chronology

```text
INITIAL_UCI5_PARENT = c47e99b8139a280c39ceacc46db738b2617866d5
FINAL_REVIEW_HARDENED_UCI5_PARENT = c1a562013d521959d92cbd7f84f615f2d120e663
UCI4_FROZEN_PARENT = 9702004a6230d6a84cc322edb48b55c14e90fe15
```

The UCI-5 runtime admission implementation was not changed by this review. The parent movement consists of CI/evidence-contract tests and workflow hardening.

## UCI-5 independent review lineage

The review found two initial CI evidence defects: the UCI-5 gate did not bind its frozen UCI-4 parent literally, and it did not lock the expected 99-test proofline cardinality.

```text
TEST_ONLY_CANDIDATE = 418a8464e1aa4ccbf6d5e052b949c8637999e71c
EXTERNAL_RED_RUN = 32374911455
EXTERNAL_RED_JOB = 96443855031
RUNTIME_BASELINE = 20/20 PASS
CI_CONTRACT = 2 FAIL
```

After frozen-parent and cardinality hardening:

```text
CANDIDATE = d0b2a6c4058b3eaaae4b22b3de7b3a8e77d3ec57
NATIVE_GREEN_RUN = 32375040447
NATIVE_GREEN_JOB = 96444278993
SCHEMAS = 7/7 PASS
PROOFLINE = 99/99 PASS
CI_GUARDS = 2/2 PASS
ARTIFACT_ID = 9408657658
ARTIFACT_ZIP_SHA256 = bae444c1cfea8f97c1fca077d4b562b07b5bd78d1149c9fc95d78aa4eee16df1
```

Stacked execution then exposed a third CI-boundary defect: the UCI-5 workflow still triggered on every pull request, including UCI-6 PRs whose base is the UCI-5 head. A third guard was preregistered before the trigger patch.

```text
TEST_ONLY_CANDIDATE = a26be961ea4392abd08cf1cf727277e5d8621bb2
NATIVE_RED_RUN = 32375582628
NATIVE_RED_JOB = 96446054566
SCHEMAS = 7/7 PASS
PROOFLINE = 99/99 PASS
CI_CONTRACT = 1 FAIL / 2 PASS
INTENDED_FAILURE = UCI-5 workflow not scoped to its frozen-parent PR branch
```

Final UCI-5 CI-contract GREEN:

```text
FINAL_UCI5_PARENT = c1a562013d521959d92cbd7f84f615f2d120e663
NATIVE_GREEN_RUN = 32375703580
NATIVE_GREEN_JOB = 96446446216
SCHEMAS = 7/7 PASS
PROOFLINE = 99/99 PASS
CI_GUARDS = 3/3 PASS
ARTIFACT_ID = 9408917009
ARTIFACT_ZIP_SHA256 = 62a811acd64681bf23f1a4ae44eb2837669b64de386bba2d044566e8eedbf0d6
```

The UCI-5 workflow is now scoped to pull requests targeting `feat/uci-4-effect-chain-integration-v1`. Downstream UCI-6 validates the inherited UCI-5 CI-contract guards directly rather than causing the UCI-5 PR-native workflow to execute under the wrong base.

## UCI-6 fail-closed parent transition

UCI-6 was first advanced to the reviewed UCI-5 lineage at merge commit `5bd2fef5a086bad383dd9dbc3343c942afb9a4cd`. Before the UCI-6 parent constant was changed, its native gate failed at exact-lineage verification as intended:

```text
UCI6_RED_RUN = 32375310769
UCI6_RED_JOB = 96445164192
CANDIDATE = 5bd2fef5a086bad383dd9dbc3343c942afb9a4cd
WORKFLOW_EXPECTED_PARENT = c47e99b8139a280c39ceacc46db738b2617866d5
ACTUAL_PR_BASE = d0b2a6c4058b3eaaae4b22b3de7b3a8e77d3ec57
RESULT = EXACT_LINEAGE_FAILURE
```

No UCI-6 semantic test result is promoted from that failed-lineage candidate.

## Final UCI-6 gate contract after this addendum

The final UCI-6 candidate must bind `c1a562013d521959d92cbd7f84f615f2d120e663` as both its Git ancestor and PR base and must execute:

```text
12 inherited/UCI-6 schemas
125 UCI-4/UCI-5/UCI-6 semantic falsifiers
3 inherited UCI-5 CI-contract guards
```

Final exact-head run IDs and artifact identities are intentionally recorded only in PR metadata after the last Git commit, so documenting the evidence does not mutate the verified tree again.

All prior UCI-6 security and epistemic non-claims remain unchanged. This addendum does not claim distributed linearizability, cross-database atomicity, authenticated database tamper resistance, production memory admission, semantic truth, or AGI.
