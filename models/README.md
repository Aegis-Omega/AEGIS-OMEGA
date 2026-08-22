# AEGIS Ω Model Artifact Store

`models/` is the repository root of truth for model artifacts used by AEGIS Ω.

This directory deliberately separates **model capability configuration**, **artifact existence**, **artifact confidentiality**, **execution readiness**, and **AEGIS authority**.

## Constitutional boundary

Model weights, provider responses, tokenizer files, prompts, and model-generated tool calls are capability artifacts / evidence only. They are never authorization, admission, effect proof, or state-transition authority.

`WEIGHTS_PRESENT != EXECUTION_AUTHORIZED`

`MODEL_OUTPUT != AUTHORITY`

`PRIVATE != UNREAL`

`VENDOR_REMOTE_ONLY != WEIGHTS_DO_NOT_EXIST`

A model may be executable only when all of the following independently hold:

1. the model is explicitly registered in `config/model-capability-registry.v1.json`;
2. its registry status is executable (`active` or an explicitly retained legacy status);
3. required local model artifacts pass `scripts/verify-model-artifacts.py` when the selected transport is local;
4. the work order independently passes the existing AEGIS capability / consequence / authorization path;
5. external effects still require the normal EffectObservation → VerifyEffect → EffectReceipt → CompleteVerification path.

## What lives in Git

Git contains the durable control plane for model artifacts:

- `models/model-artifacts.v1.json` — canonical artifact index;
- public upstream identity/revision where applicable;
- opaque private source identity + content root for operator-private checkpoints;
- license or private-rights classification;
- expected SHA-256 digests for admitted files;
- mirror coordinates and confidentiality state;
- hydration / verification tooling;
- receipts and schemas that prove what was actually present.

Large raw weights are **not** written into ordinary Git history. The canonical AEGIS design is **repo-rooted** rather than **Git-object-rooted**:

- the hydrated worktree path is `models/weights/<package-id>/`;
- public open weights may use digest-bound repository release assets;
- private operator weights use an operator-private store or an encrypted repository artifact transport;
- the public repository may contain only non-secret manifests, opaque references and hashes for private checkpoints;
- plaintext private weights must never be published merely because the control repository is public;
- hydration reconstructs exact model bytes into the repository worktree and verifies them before use.

## Weight availability classes

- `PUBLIC_OPEN_WEIGHTS` — public downloadable checkpoint with source/revision/license evidence. It may be publicly mirrored after digest closure and license verification.
- `PRIVATE_OPERATOR_WEIGHTS` — a real operator-controlled checkpoint. It is identified by an opaque private source reference, deterministic content root and per-file SHA-256 digests. A public URL is neither required nor desirable. Local routing requires `PRIVATE_MIRRORED_VERIFIED` plus byte verification.
- `VENDOR_REMOTE_ONLY` — this particular registered execution package represents the vendor/API surface. It makes **no claim** that equivalent, related, privately-held or independently-created weights do not exist elsewhere.
- `MANIFEST_ONLY_PENDING_PIN` — an artifact is known but exact source/digest closure is incomplete; local execution fails closed.
- `UNVERIFIED_UNKNOWN` — artifact existence or identity has not been established strongly enough for use.

## Public vs private evidence

Public/vendor packages require primary provider/upstream evidence where relevant.

Private packages may use `OPERATOR_PRIVATE_*` evidence records with opaque references instead of public URLs. A private artifact's existence is established from its bytes and content root, not from whether outsiders can download it.

Capability claims remain separate from artifact existence. Possessing weights proves that the artifact exists; it does not by itself prove that the model satisfies `planner`, `coder`, reasoning, safety, or other capability requirements. Those require their own source/evaluation evidence.

## Current initial packages

- Gemma 4 E2B IT — `PUBLIC_OPEN_WEIGHTS`, Apache-2.0, exact source revision and primary weight SHA pinned.
- DeepSeek V4 Flash / Pro — `PUBLIC_OPEN_WEIGHTS`, MIT; local vendoring remains fail-closed until complete shard digest closure is recorded.
- GPT, Claude and managed Qwen API entries — currently represented by `VENDOR_REMOTE_ONLY` packages for their provider execution surfaces. This classification does not deny the existence of any separately held private checkpoint.
- operator-private checkpoints — supported as first-class packages through `operator-local`; actual package records are added only after their real bytes are located and digest-bound.

## Registering an operator-private checkpoint

Run `scripts/register-private-model-artifact.py` on the machine that actually has the checkpoint bytes. It computes every file digest and a deterministic private content root, emits a repo-safe manifest fragment and receipt, and intentionally does not upload the checkpoint or disclose the private source path.

A private checkpoint moves conceptually through:

`PRIVATE_BYTES_FOUND → DIGEST_BOUND → PRIVATE_SOURCE_REGISTERED → PRIVATE_MIRRORED_VERIFIED → LOCAL_VERIFIED → EVALUATED → EXPLICITLY_ACTIVATED`

No step implies the next one.

## Future models

Every future model family follows the same evidence-first path:

`discover/locate → bind source or private content root → artifact manifest → capability/evaluation evidence → candidate → explicit activation → bounded work order → evidence/receipt`

A new release or newly-discovered private checkpoint may change configuration. It may not change AEGIS authority semantics.
