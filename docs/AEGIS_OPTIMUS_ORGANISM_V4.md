# AEGIS Ω | OPTIMUS EVOLUTION · Organism V4

**Date:** 2026-11-01. **Scope:** bounded offline candidate, not GitHub-admitted. **Claims:** 78/78 local Node tests PASS on V4 source; no native full-repo CI or production execution.

## Historical source and reason for V4

Source base: V3 zip `AEGIS_OPTIMUS_ORGANISM_V3_20261101.zip` (66/66 checkpoint). Existing AEGIS metacognitive provider: `Aegis-Omega/AEGIS-OMEGA` PR #560 HEAD `f420d42dd775ce3b3d82da6b9ed5dfca2534d988` (read only). Its actual `evidence-cycle.mjs` / `evidence-ledger.mjs` / `chain.mjs` are **not** bundled here. The import-only CLI expects those exact native modules in their existing paths. No new branch or protected-main mutation is authorized. The source parent is an exact PR #560 candidate baseline.

## Integrated causal cycle

`native evidence snapshot → actual source byte digest → native receipt and ledger → chain mirror → probabilistic self-model → safe advisory PROPOSE → deterministic sandbox file → re-read and hash → outcome receipt → bounded state and adaptive action-calibration`.

- `organism-core.mjs` now binds `last_action_kind` to the hash-linked state; preserves valid V3 checkpoint hashes by treating this new field as optional on historical entries. Legacy pending states without a known kind are **not** automatically replayed.
- `organism-coordinator.mjs` adds a single-writer cycle lock, calls the existing bridge, and coordinates a safe proposal with feedback. Production/network side effects are out of scope.
- `organism-motor.mjs` offers idempotent `resumeOrPrepareProposal` that **never silently overwrites** an existing candidate, and compares both the decision and evidence IDs.
- Before recovery, the coordinator re-verifies the **same original receipt** against persisted state; rechecks byte-level source evidence; checks the ledger via an injected verifier; confirms the corresponding ledger transition is recorded in a chain whose certification succeeds. It does not re-call a native provider to fabricate replacement evidence.
- A controlled failure after the decision or after writing the proposal leaves the original pending action intact. A retry reuses it, or HOLDs when any necessary evidence is damaged.
- `scripts/local-organism-v4.mjs` is a native-adapter entry point, not a replacement evidence implementation. It imports existing PR #560 sources; it is syntax-checked, but **not run on a full native checkout** in this environment.

## Tested obligations (local)

`node --test tests/*.test.mjs` → **78 passed, 0 failed**.

New failure-injection tests: crash after decision, crash after motor, duplicate observation, modified proposal, source drift, missing ledger, single-writer exclusion, legacy V3 exact-hash loading, and hold for nonmotor actions. All V3 tests remain green.

## Security and correctness boundaries

- A sandbox proposal readback verifies only a **local artifact**, not the accuracy of its source claim and not the success of external execution. It does **not** prove phenomenal consciousness or autopoiesis.
- The contract tests use injected simplified evidence-cycle/ledger ports; they are **not** native CI receipts. In the native CLI, the real `runEvidenceCycle`, `verifyReceipt`, `certifyLedger` are required.
- Offline fixture hashes and unsigned JSON anchors are tamper-evident against accidental or uncoordinated modification, but cannot stop an attacker able to rewrite all files. No trusted hardware root or signature authority was invented.
- Native `evidence-cycle.mjs` currently can append its ledger before chain mirroring; if it crashes between these steps, a duplicate retry may skip mirroring. Organism V4 **HOLDs** that case rather than silently repairing it. A native source-bound transaction repair and replay test are still OPEN.
- Native `.claude/hooks/user-prompt-intake.sh` can report initial success when certification fails; native `.claude/metacog/chain.mjs` NFC canonicalization differs from `sovereign-omega-v2/src/core/canonicalize.ts` on decomposed Unicode. Neither is silently patched here.
- Actual billed token usage is not measured; energy is a synthetic finite allocation, not money or actual computation. No new authority, deployment, cloud service, webhook, credential, paid inference, protected-main change or self-preservation privilege.
- The native environment, exact HEAD deployment, provider-independent outcome proof, full typecheck, reboot recovery under native CI and cross-platform canonicalization remain OPEN.

## Quality vs efficiency

Efficiency is never substituted for factual correctness. A proposed action must satisfy explicit quality/reliability constraints, then optimize expected value per finite allocation. V3's adaptive controller improves held-out regime-shift success but trades away stable-regime performance. These synthetic results are hypothesis-generating, not universal optimization.

## Reproduce

From this extracted package:
```
node --test tests/*.test.mjs
node --check scripts/local-organism-v4.mjs
sha256sum -c docs/AEGIS_OPTIMUS_ORGANISM_V4_SHA256SUMS
```

Native acceptance (OPEN): apply this patch to the *existing authorized candidate branch* at the verified exact HEAD, run actual `evidence-cycle.mjs` and chain/recovery tests against the checked-out sources, then inspect GitHub Actions and compare source hashes. Do not merge or deploy based on local results alone.
