# Kernel One — Constitutional Execution Kernel

**Epistemic tier:** T2. This is a verified local governance kernel proposed to canonical `main`; it is not a deployed production authority.

Kernel One admits or rejects model proposals against a constitutional manifest. Accepted transactions persist the proposal artifact, a content-bound `WitnessEnvelope`, and its HMAC signature in one SQLite transaction. Validation failures return `RECONCILED_FALLBACK` and do not write an accepted witness.

```text
READ → ASSESS → T0_CHECK → LOCK → PROPAGATE → HARMONIZE
```

## Admission gate

`KernelOneEngine.process_transaction(request, raw_model_response)` requires:

1. A non-empty `request_id`, task string, and four finite numeric metrics.
2. Residual delta below `safety.delta_critical` in `INDEX.yaml`.
3. Exactly `{plan, output, tool_calls}` from the proposal engine.
4. No frozen or unregistered mutation target.
5. A configured, non-compromised signing identity.

Missing constitutional files, missing signing configuration, empty request IDs, malformed proposals, adverse entropy, and invalid mutation targets fail closed.

## Signing configuration

Runtime construction requires:

```text
AEGIS_KERNEL_SIGNING_KEY       secret key material
AEGIS_KERNEL_SIGNING_KEY_ID    versioned key identifier
```

The signing algorithm is fixed to `hmac-sha256`. `AEGIS_KERNEL_SIGNING_ALGORITHM`, when present, must equal that exact value.

There is no built-in, development, or historical fallback secret. The disclosed historical identity is explicitly rejected:

```text
kernel-hmac-v0-compromised
```

Tests inject `kernel-hmac-test-v1` and fixture key bytes directly; those values are not runtime defaults.

## Integrity utilities and evidentiary record

`validator.py` provides deterministic, read-only integrity primitives:

```python
sha256_file(path)
validate_file(path, expected_digest)
```

They identify and verify file bytes. They do not grant authority.

The authoritative evidence object is the signed envelope:

```text
WitnessEnvelope {
  schema_version
  request_id
  artifact_path
  artifact_sha256
  observed_at
  sequence
  parent_receipt_hash
  key_id
  algorithm
}
```

The envelope is serialized as sorted, whitespace-free UTF-8 JSON. Its receipt hash is `SHA256(canonical_envelope)`. The signature is `HMAC-SHA256(key, canonical_envelope)`. Timestamp, sequence, parent receipt, key ID, algorithm, artifact path, and artifact digest are all signature-bound.

Precedence is explicit:

```text
sha256_file / validate_file = integrity utilities
WitnessEnvelope             = evidentiary record
```

The rejected production curation's request-handling path is not imported.

## Ledger

`init_db.py` creates three linked tables:

- `witnesses` — accepted transition record;
- `artifacts` — proposal plan, output, and tool calls;
- `witness_envelopes` — canonical envelope, key ID, algorithm, signature, sequence, and parent receipt.

Insertion occurs under `BEGIN IMMEDIATE`; all three records commit or roll back together. `memory_store.sqlite` and its WAL/SHM files are runtime state and remain excluded from Git.

## Verification

```bash
cd kernel-one
python test_kernel_one.py
```

The gate proves:

- the recovered rescue lineage remains 9/9;
- missing signing configuration fails deterministically;
- the compromised key ID is rejected;
- missing and empty request IDs are denied;
- the former `missing_request_id` bypass is closed;
- file, timestamp, parent-receipt, and key-ID mutation invalidate verification;
- the signed envelope is persisted atomically;
- production code contains no fallback signing secret.

The dedicated GitHub check is `aegis / kernel-one`.

## Provenance

The package was recovered from operator-local development that had not reached canonical GitHub `main`. The selected source lineage is rescue commit `0f6d316`, which passes all nine original adversarial assertions. The parallel curation `ea1c660` remains rejected because its request path allowed a reproducible missing-`request_id` bypass.

Two recovered SQLite ledgers remain out-of-tree forensic evidence:

| File | SHA-256 |
|---|---|
| `memory_store.sqlite` | `359e8ac7483970a7ac27b186269b8d4a27be69f9fca8957e209b3cc1651deb58` |
| `memory_store (1).sqlite` | `bb3e4d8acddf504dd8f882397f91c730f20e7a4051e016cd379c41b1ecb6c46e` |

The ZIP archives and local Git objects remain historical provenance sources, not implementation-admission dependencies.
