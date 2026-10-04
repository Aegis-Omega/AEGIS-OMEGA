# UCI-6 Collective Memory Admission — Implementation Plan

> **Execution mode:** test-first, exact-head, fail-closed. UCI-5 remains the only admission authority input; memory never authorizes itself.

**Goal:** implement a local reference memory boundary with a strict split between non-authoritative quarantined evidence and canonical evidence memory projected only from an already admitted UCI-5 transition. Revocation and supersession are append-only admitted control events; history is never destructively rewritten.

**Exact parent:** `#277@c47e99b8139a280c39ceacc46db738b2617866d5`

## Core theorem

```text
Memory(x) != Authority(x)
CanonicalMemory(x) != Truth(x)
ProviderContribution(x) -> QuarantinedEvidence(x)
QuarantinedEvidence(x) -/-> CanonicalMemory(x)
CanonicalMemory(x) requires AdmittedProjection(x)
```

No retrieved memory record may grant capability, authority, execution permission, effect truth, or epistemic promotion by itself.

## Architecture

### 1. Quarantine plane

`QuarantinedEvidenceMemoryRecordV1` is immutable evidence metadata only. It binds:

```text
record_kind = QUARANTINED_EVIDENCE_MEMORY_RECORD_V1
content_digest
media_type
producer_ref
source_ref
memory_class
epistemic_tier
authority = EVIDENCE_ONLY
authority_weight_bps = 0
```

The record root is content-addressed under `AEGIS_QUARANTINED_MEMORY_RECORD_V1`.

Quarantine insertion does **not** require admission because insertion itself cannot affect authority or canonical state. Duplicate identical roots are idempotent; conflicting reinterpretation is impossible because the root commits the metadata.

### 2. Projection request

`MemoryProjectionRequestV1` exists before admission and binds:

```text
request_kind = MEMORY_PROJECTION_REQUEST_V1
quarantine_root
content_digest
memory_class
epistemic_tier
memory_policy_commitment
nonce
```

Its root uses `AEGIS_MEMORY_PROJECTION_REQUEST_V1` and becomes the exact `TransitionIdentity.action_digest` for the projection transition.

Canonical projection requires:

```text
transition.action_digest == projection_request.root
admission_record.transition_id == transition.root
admission_record.admission_policy_commitment == uci5_admission_policy_commitment()
admission_record.next_state_commitment is already established by UCI-5
projection_request.memory_policy_commitment == current UCI-6 memory policy
quarantine metadata == projection request metadata
```

The projection store does not trust a caller assertion that a transition was admitted; it requires an exact nominal `AdmissionRecordV1` whose root and transition binding validate.

### 3. Canonical evidence memory

`CanonicalMemoryRecordV1` is generated only after the projection checks pass. It binds:

```text
record_kind = CANONICAL_MEMORY_RECORD_V1
projection_request_root
source_quarantine_root
content_digest
memory_class
epistemic_tier
authority = EVIDENCE_ONLY
authority_weight_bps = 0
source_transition_id
source_admission_root
memory_policy_commitment
sequence
prior_memory_event_root
```

Dedicated hash domain: `AEGIS_CANONICAL_MEMORY_RECORD_V1`.

Canonical means admitted into the persistent memory index. It does **not** mean proposition truth or permission.

### 4. Append-only control plane

`MemoryControlRequestV1`:

```text
request_kind = MEMORY_CONTROL_REQUEST_V1
operation = REVOKE | SUPERSEDE
target_memory_root
replacement_memory_root = null | canonical root
memory_policy_commitment
nonce
```

Rules:
- `REVOKE` requires replacement = null.
- `SUPERSEDE` requires a different, currently ACTIVE canonical replacement.
- target must currently be ACTIVE.
- the control request root must equal the admitted transition's `action_digest`.
- the exact `AdmissionRecordV1` must bind that transition.

`MemoryControlRecordV1` is generated append-only and binds the request root, target/replacement, admitted transition/root, sequence and prior event root.

No delete/update rewrites the original canonical record. Effective status is derived from the event log:

```text
ACTIVE | REVOKED | SUPERSEDED
```

### 5. Local reference store

`LocalSqliteCollectiveMemoryStoreV1` uses a separate SQLite database with:

```text
memory_state(singleton=1, memory_policy_commitment, sequence, last_event_root)
quarantine_records(memory_root PK, payload_json)
canonical_records(memory_root PK, projection_request_root UNIQUE,
                  source_transition_id UNIQUE, source_admission_root UNIQUE,
                  payload_json)
memory_control_records(event_root PK, request_root UNIQUE,
                       source_transition_id UNIQUE, source_admission_root UNIQUE,
                       target_memory_root, replacement_memory_root, sequence,
                       payload_json)
```

Canonical projection/control operations use `BEGIN IMMEDIATE` and update the memory event chain atomically with their generated record.

## UCI6_MEMORY_POLICY_V1

The policy commitment must explicitly state:

```text
quarantine_write = EVIDENCE_ONLY_NO_AUTHORITY
canonical_projection = REQUIRES_UCI5_ADMITTED_ACTION
control_event = REQUIRES_UCI5_ADMITTED_ACTION
retrieval_authority = EVIDENCE_ONLY
canonical_truth_claim = FORBIDDEN
self_authorization = FORBIDDEN
tier_promotion_during_projection = FORBIDDEN
destructive_delete = FORBIDDEN
accepted_uci5_admission_policy_commitment = current UCI-5 policy root
production_memory_backend = NOT_ESTABLISHED
```

## TDD tasks

### Task 1 — RED import boundary

Create `sovereign-omega-v2/python/tests/test_uci6_collective_memory.py` before `harness/sdk/collective_memory.py` exists.

First exact-head witness must fail specifically with:

```text
ModuleNotFoundError: No module named 'harness.sdk.collective_memory'
```

### Task 2 — preregister behavioral falsifiers

Before implementation, add tests covering at minimum:

- quarantine insert is evidence-only and authority weight zero;
- identical quarantine insert is idempotent;
- quarantine cannot be promoted without exact UCI-5 admission;
- projection request root must equal transition action digest;
- AdmissionRecord transition mismatch rejects;
- UCI-5 admission-policy mismatch rejects;
- current memory-policy mismatch rejects;
- content/class/tier mismatch between quarantine and projection rejects;
- projection cannot promote epistemic tier;
- successful projection emits one canonical record and advances one event sequence;
- duplicate projection/replay rejects;
- canonical retrieval remains evidence-only;
- direct caller construction cannot insert arbitrary canonical record;
- REVOKE requires an admitted control request and leaves canonical history intact;
- SUPERSEDE requires an admitted control request and ACTIVE replacement;
- inactive target cannot be controlled twice;
- replacement cannot equal target;
- supersession effective status points to replacement;
- injected fault after record insert rolls back event-chain update and record;
- two store handles racing the same admitted projection yield exactly one canonical record;
- reopen with conflicting memory-policy commitment fails closed;
- all serialized schemas reject unknown fields and wrong discriminators.

### Task 3 — implementation

Create:

```text
harness/sdk/collective_memory.py
schemas/quarantined-evidence-memory-record.v1.schema.json
schemas/memory-projection-request.v1.schema.json
schemas/canonical-memory-record.v1.schema.json
schemas/memory-control-request.v1.schema.json
schemas/memory-control-record.v1.schema.json
```

No #267 hackathon/cloud code is merged wholesale. Its stale-state/policy/epoch/replay fail-closed pattern is source material only.

### Task 4 — exact-head gate

Create `.github/workflows/uci-6-collective-memory-contract.yml`:

- exact candidate/parent binding;
- pinned pytest/jsonschema;
- validate the five UCI-6 schemas plus inherited seven UCI-4/UCI-5 schemas;
- run UCI-6 tests + complete UCI-5/UCI-4 regression set;
- negative schema vectors;
- evidence-only artifact;
- explicit non-claims.

### Task 5 — audit ledger

Create `docs/audits/2026-08-20-uci6-collective-memory-lineage-ledger.md` with all RED/GREEN exact SHA/run/artifact evidence and adversarial findings.

## Acceptance ledger

Only after final exact-head GREEN:

```text
UCI6_QUARANTINE_EVIDENCE_STORE = IMPLEMENTED_AND_TESTED_REFERENCE
UCI6_CANONICAL_MEMORY_PROJECTION = REQUIRES_EXACT_UCI5_ADMISSION
UCI6_MEMORY_SELF_AUTHORIZATION = FORBIDDEN_AND_TESTED
UCI6_TIER_PROMOTION_DURING_PROJECTION = FORBIDDEN_AND_TESTED
UCI6_REVOCATION = APPEND_ONLY_AND_ADMISSION_BOUND
UCI6_SUPERSESSION = APPEND_ONLY_AND_ADMISSION_BOUND
UCI6_RETRIEVAL_AUTHORITY = EVIDENCE_ONLY
UCI6_EVENT_REPLAY = FORBIDDEN_AND_TESTED

CANONICAL_MEMORY_IMPLIES_TRUTH = FALSE
MEMORY_CAN_GRANT_AUTHORITY = FALSE
DISTRIBUTED_MEMORY_LINEARIZABILITY = NOT_ESTABLISHED
AUTHENTICATED_DATABASE_TAMPER_RESISTANCE = NOT_ESTABLISHED
VECTOR_RETRIEVAL_SEMANTIC_CORRECTNESS = NOT_ESTABLISHED
PRODUCTION_MEMORY_ADMISSION = NOT_ESTABLISHED
```
