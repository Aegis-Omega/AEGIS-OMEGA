# UCI-6 Parent Review Hardening Addendum

Date context: 2026-08-20

This addendum supersedes only the final stacked-parent identities recorded in the earlier UCI-6 implementation plan and lineage ledger. Those documents remain historical records of the parent used during initial UCI-6 implementation. Subsequent independent review hardened UCI-5 CI evidence first, then UCI-4 effect-evidence integrity, requiring two fail-closed downstream restacks.

## Parent chronology

```text
INITIAL_UCI5_PARENT = c47e99b8139a280c39ceacc46db738b2617866d5
FIRST_REVIEWED_UCI5_PARENT = c1a562013d521959d92cbd7f84f615f2d120e663
HISTORICAL_UCI4_PARENT = 9702004a6230d6a84cc322edb48b55c14e90fe15
HARDENED_UCI4_PARENT = bda5c5369b15ec91f2651ddbf6d219f6b7a1d0f6
CURRENT_RESTACKED_UCI5_PARENT = be07805af9887ff15272167740b07cf958c3137e
```

No parent movement is treated as evidence by assertion. Each transition requires real Git ancestry, an intentional stale-parent RED, an updated frozen-parent contract, and a fresh exact-head GREEN.

## First UCI-5 independent review lineage

The first review found three CI/evidence-contract defects: the UCI-5 gate did not bind its frozen UCI-4 parent literally, it did not lock the expected 99-test proofline cardinality, and its pull-request trigger was too broad for a stacked workflow.

```text
INITIAL_CI_RED = 418a8464e1aa4ccbf6d5e052b949c8637999e71c
EXTERNAL_RED_RUN = 32374911455
RUNTIME_BASELINE = 20/20 PASS
CI_CONTRACT = 2 FAIL

TRIGGER_SCOPE_RED = a26be961ea4392abd08cf1cf727277e5d8621bb2
NATIVE_RED_RUN = 32375582628
PROOFLINE = 99/99 PASS
CI_CONTRACT = 1 FAIL / 2 PASS

FIRST_REVIEWED_UCI5_PARENT = c1a562013d521959d92cbd7f84f615f2d120e663
NATIVE_GREEN_RUN = 32375703580
NATIVE_GREEN_JOB = 96446446216
SCHEMAS = 7/7 PASS
PROOFLINE = 99/99 PASS
CI_GUARDS = 3/3 PASS
ARTIFACT_ID = 9408917009
ARTIFACT_ZIP_SHA256 = 62a811acd64681bf23f1a4ae44eb2837669b64de386bba2d044566e8eedbf0d6
```

## UCI-4 proof-integrity hardening

Independent UCI-4 review later found that the earlier 79-test GREEN still allowed three effect-evidence integrity gaps and three CI-contract gaps:

- a caller could structurally fabricate an `EffectWitness` carrying the supported adapter identity/version and have it accepted as effect evidence;
- filesystem observation used a path-resolution/open sequence that was not descriptor-relative and race-resistant;
- hashing read the whole file without an explicit observation-size bound;
- the UCI-4 workflow used a dynamic parent instead of the frozen parent literal;
- the workflow triggered on downstream PRs;
- the proofline cardinality was not locked.

All six falsifiers were preregistered before the production patch.

```text
UCI4_SECURITY_RED = 4c805dff810b0493612ac96e1b7275caeac8b005
UCI4_RED_RUN = 32381803664
UCI4_RED_JOB = 96466565104
SCHEMAS = 6/6 PASS
PRIOR_BASELINE = 79 PASS
NEW_SECURITY_CI_FALSIFIERS = 6 FAIL
ARTIFACT_ID = 9411298497
ARTIFACT_ZIP_SHA256 = e7d41b6f5ff788d048c3656a6d20989411a9782c64004eb2fc0c3caefd1707c7

HARDENED_UCI4_PARENT = bda5c5369b15ec91f2651ddbf6d219f6b7a1d0f6
UCI4_GREEN_RUN = 32382334592
UCI4_GREEN_JOB = 96468341013
EXACT_LINEAGE = PASS
SCHEMAS = 6/6 PASS
HARDENED_PROOFLINE = 85/85 PASS
ARTIFACT_ID = 9411502359
ARTIFACT_ZIP_SHA256 = a8ef6d63d292914f8b7e650120a8e64f1125b20b49aeca6e2f7ae518718b6a2c
```

The hardened local/reference effect boundary now uses descriptor-relative POSIX `O_NOFOLLOW` path walking, bounded streaming hashing, detected-concurrent-change rejection, and a process-local issued-witness registry. These are not represented as cross-process cryptographic attestation or an atomic privileged-adversary filesystem snapshot proof.

## UCI-5 restack onto hardened UCI-4

UCI-5 was advanced with a true two-parent merge commit rather than file-copy lineage laundering:

```text
UCI5_RESTACK_MERGE = d8f17f6ead03e8c6491bf80567e0af6a753c4eac
PARENTS = c1a562013d521959d92cbd7f84f615f2d120e663 + bda5c5369b15ec91f2651ddbf6d219f6b7a1d0f6
```

Before updating its frozen-parent constant, the native gate failed exactly as intended:

```text
UCI5_RESTACK_RED_RUN = 32382784974
UCI5_RESTACK_RED_JOB = 96469836763
WORKFLOW_EXPECTED_PARENT = 9702004a6230d6a84cc322edb48b55c14e90fe15
ACTUAL_PR_BASE = bda5c5369b15ec91f2651ddbf6d219f6b7a1d0f6
RESULT = EXACT_LINEAGE_FAILURE
ARTIFACT_ID = 9411673090
ARTIFACT_ZIP_SHA256 = 7895d71a1deb22b5d5c39a4d408690740ad99a3560bf3fbaf6ef054a6b0324e4
```

The inherited semantic cardinality then changed deterministically from `99` to `105` because hardened UCI-4 contributes six additional falsifiers while the UCI-5-specific set remains 20.

```text
CURRENT_RESTACKED_UCI5_PARENT = be07805af9887ff15272167740b07cf958c3137e
UCI5_GREEN_RUN = 32382929713
UCI5_GREEN_JOB = 96470309046
EXACT_LINEAGE = PASS
SCHEMAS = 7/7 PASS
PROOFLINE = 105/105 PASS
CI_GUARDS = 3/3 PASS
ARTIFACT_ID = 9411735542
ARTIFACT_ZIP_SHA256 = 7c3b5774b2e4d1262f656deda8a0dcc072f231a86e8b82049efdf95834ef7af2
```

Exact-head Coq/Kernel/Coordinator status for this parent is recorded in PR metadata after the workflows finish; no future result is asserted in this tree-bound addendum.

## UCI-6 second fail-closed parent transition

UCI-6 was restacked onto the current UCI-5 parent with another true two-parent merge commit. The parent delta from `c1a562…` to `be07805…` was exactly six files: four UCI-4 hardened files plus the UCI-5 workflow and its CI-contract test.

```text
UCI6_RESTACK_MERGE = 757be2bc6241a92c4e0393096e8db180442cdd7a
PARENTS = 33e2fc03c035185a194b40301c0f0b575b01946e + be07805af9887ff15272167740b07cf958c3137e
UCI6_RESTACK_RED_RUN = 32383209016
UCI6_RESTACK_RED_JOB = 96471230807
WORKFLOW_EXPECTED_PARENT = c1a562013d521959d92cbd7f84f615f2d120e663
ACTUAL_PR_BASE = be07805af9887ff15272167740b07cf958c3137e
RESULT = EXACT_LINEAGE_FAILURE
ARTIFACT_ID = 9411839846
ARTIFACT_ZIP_SHA256 = 247b686b2d31fe1bef2802e5f3f71dd0fc4441c779fa6ae8df112b6281a60885
```

No UCI-6 semantic result is promoted from that failed-lineage candidate.

## Final UCI-6 gate contract after this addendum

The final UCI-6 candidate must bind `be07805af9887ff15272167740b07cf958c3137e` as both its Git ancestor and PR base and must execute:

```text
12 inherited/UCI-6 schemas
131 UCI-4/UCI-5/UCI-6 semantic falsifiers
3 inherited UCI-5 CI-contract guards
```

The count is `105` inherited UCI-4/UCI-5 falsifiers plus the unchanged `26` UCI-6 falsifiers.

Final exact-head run IDs and artifact identities are intentionally recorded only in PR metadata after the last Git commit, so documenting final evidence does not mutate the verified tree again.

All prior UCI-6 security and epistemic non-claims remain unchanged. This addendum does not establish cross-process effect-witness attestation, malicious same-process Python isolation, atomic filesystem snapshots, distributed linearizability, cross-database atomicity, authenticated database tamper resistance, production memory admission, semantic truth, or AGI.
