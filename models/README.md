# AEGIS Ω Model Artifact Store

`models/` is the repository root of truth for model artifacts used by AEGIS Ω.

This directory deliberately separates **model capability configuration** from **model bytes** and from **AEGIS authority**.

## Constitutional boundary

Model weights, provider responses, tokenizer files, prompts, and model-generated tool calls are capability artifacts / evidence only. They are never authorization, admission, effect proof, or state-transition authority.

`WEIGHTS_PRESENT != EXECUTION_AUTHORIZED`

`MODEL_OUTPUT != AUTHORITY`

A model may be executable only when all of the following independently hold:

1. the model is explicitly registered in `config/model-capability-registry.v1.json`;
2. its registry status is executable (`active` or an explicitly retained legacy status);
3. required local model artifacts pass `scripts/verify-model-artifacts.py` when the selected transport is local;
4. the work order independently passes the existing AEGIS capability / consequence / authorization path;
5. external effects still require the normal EffectObservation → VerifyEffect → EffectReceipt → CompleteVerification path.

## What lives in Git

Git contains the durable control plane for model artifacts:

- `models/model-artifacts.v1.json` — canonical artifact index;
- exact upstream repository and revision where known;
- license identifier and weight-availability class;
- expected SHA-256 digests for pinned files;
- repo-owned mirror/release coordinates when vendored;
- hydration / verification tooling;
- receipts and schemas that prove what was actually present.

Large raw weights are **not** written into ordinary Git history. GitHub blocks regular Git objects above 100 MiB and very large histories damage repository operability. The canonical AEGIS design is therefore **repo-rooted** rather than **Git-object-rooted**:

- the local worktree path is `models/weights/<package-id>/`;
- the durable mirror is owned by this repository (GitHub release assets, chunked when necessary);
- Git tracks the manifest and hashes that bind those bytes;
- hydration reconstructs the exact model bytes into the repository worktree and verifies them before use.

This keeps a hydrated AEGIS checkout self-contained without making every clone download hundreds of gigabytes.

## Weight availability classes

- `OPEN_WEIGHTS` — upstream publishes downloadable model weights under a redistributable/open license. These may be mirrored after digest and license verification.
- `REMOTE_ONLY_NO_PUBLIC_WEIGHTS` — the provider does not publish usable model weights. AEGIS stores only the provider contract, pinned model identifier, capability evidence and execution receipts. Creating fake local weights is forbidden.
- `MANIFEST_ONLY_PENDING_PIN` — open weights are known to exist, but exact source revision / complete shard digest closure is not yet established. Runtime local execution fails closed.

## Current initial packages

- Gemma 4 E2B IT — open weights, Apache-2.0, exact source revision and primary weight SHA pinned; ready for controlled vendoring.
- DeepSeek V4 Flash — open weights, MIT; 46-shard checkpoint. Registry entry exists but local vendoring remains fail-closed until complete source/shard closure is recorded.
- GPT and Claude families — remote-only because public model weights are not available. Their API/provider contracts remain first-class AEGIS model packages, but never pretend to be local checkpoints.

## Future models

Every future model family follows the same path:

`discover → source/license verify → artifact manifest → capability manifest → candidate → evaluation → explicit activation → bounded work order → evidence/receipt`

A new release may change a configuration record. It may not change AEGIS authority semantics.
