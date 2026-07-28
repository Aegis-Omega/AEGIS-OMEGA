# ADR-0022: Cross-runtime authoritative receipt provenance

Status: Accepted for implementation; authoritative projection admission pending

Depends on: ADR-0021

## Context and terminology

The outcome-evidence replay boundary can authenticate a verifier's certificate and persist it add-only, but the original Python lease and mutation receipts are not independently verifiable after process restart. Their validation depends on in-memory issuance sets. Consequently, a certificate that names those roots is verifier-attested T2 evidence; it is not proof that another runtime reconstructed the native lease or mutation event.

This ADR closes the requested "T2 to T3 provenance boundary" by defining independently signed, content-addressed, cross-runtime receipts. Here, T2 and T3 describe provenance-assurance stages only. They do not refer to the repository epistemic taxonomy, where `T3` means research conjecture. Passing this ADR does not make a conjecture authoritative and does not change the epistemic tier of the outcome comparator.

## Decision

Python and TypeScript use one closed I-JSON receipt contract:

- `schemas/cross-runtime-receipt-envelope.v1.schema.json` defines signed lease and mutation lifecycle receipts.
- `schemas/receipt-trust-registry.v1.schema.json` defines the operator-signed, versioned trust roots allowed to verify those receipts.
- TypeScript validates values with the existing strict I-JSON boundary and serializes them with the existing RFC 8785 JCS implementation. No receipt-specific serializer is permitted.
- Python applies the equivalent closed-I-JSON restrictions before its existing canonical byte path. It must not introduce a competing receipt serializer.
- Every object is checked for its exact schema keys before hashing or signature verification. Malformed, aliased, non-I-JSON, or schema-drifted values fail closed.

The receipt resolver verifies facts. It does not grant authority, execute a provider action, mutate canonical state, or promote metacognitive competence.

## Receipt envelope

The exact top-level `Cross-Runtime Authoritative Receipt Envelope V1` fields are:

```text
schema_version = "1.0.0"
receipt_kind
receipt_body
proof
receipt_id
```

`receipt_kind` is exactly one of:

```text
LEASE_ISSUED
LEASE_ISSUANCE_DENIED
LEASE_RENEWED
LEASE_RENEWAL_DENIED
LEASE_EXPIRED
LEASE_REVOKED
MUTATION_ADMITTED
MUTATION_DENIED
MUTATION_COMPLETED
MUTATION_CANCELLED
MUTATION_FAILED
```

The exact `receipt_body` fields are:

```text
receipt_sequence
actor_identity_root
session_identity_root
workspace_identity_root
holon_identity_root
authority_domain
authority_level
authority_receipt_hash
lease_id
lease_generation
fencing_token
lease_authorization_receipt_hash
parent_receipt_hash
observed_state_root
expected_state_root
action_digest
before_state_root
after_state_root
result_digest
timestamp_ms
expires_at_ms
nonce
outcome
denial_codes
```

The actor, session, workspace, and holon roots and `lease_id` are always resolved, non-zero SHA-256 values. `authority_level` is one of `D0` through `D4`. Sequence, generation, and time fields are canonical unsigned decimal strings, not JSON numbers. The fencing token and all receipt, state, action, and result bindings are lowercase SHA-256 values. `denial_codes` is a unique canonical array whose implementation normalization is deterministic.

`LEASE_ISSUANCE_DENIED` carries the zero fencing token because no lease was created. Every other receipt kind carries a non-zero presented or issued fence. Lease receipts carry zero `authority_receipt_hash` and `lease_authorization_receipt_hash`; mutation receipts require both links to be non-zero. These absence rules are enforced by the JSON schema and both runtimes, not inferred by the resolver.

The exact `proof` fields are:

```text
algorithm = "Ed25519"
signer_key_id
verifier_identity_root
trust_registry_version
trust_registry_root
signature
```

The proof does not carry an independently trusted public key. The resolver obtains that key only from the authenticated registry named by `trust_registry_root`, then checks the key ID, verifier identity, authority domain, receipt kind, validity interval, and status.

## Outcome and lifecycle invariants

Receipt kind and outcome are paired as follows:

| Receipt kind | Required outcome |
|---|---|
| `LEASE_ISSUED` | `ADMITTED` |
| `LEASE_ISSUANCE_DENIED` | `DENIED` |
| `LEASE_RENEWED` | `ADMITTED` |
| `LEASE_RENEWAL_DENIED` | `DENIED` |
| `LEASE_EXPIRED` | `EXPIRED` |
| `LEASE_REVOKED` | `REVOKED` |
| `MUTATION_ADMITTED` | `ADMITTED` |
| `MUTATION_DENIED` | `DENIED` |
| `MUTATION_COMPLETED` | `COMPLETED` |
| `MUTATION_CANCELLED` | `CANCELLED` |
| `MUTATION_FAILED` | `FAILED` |

`ADMITTED` and `COMPLETED` outcomes require an empty denial-code array. `DENIED`, `EXPIRED`, `REVOKED`, `CANCELLED`, and `FAILED` outcomes require at least one code. Positive lease and mutation receipts require resolved fencing, state, action, and applicable authority or lease-authorization bindings. A zero hash can represent only an explicitly absent predecessor or evidence link allowed for that receipt kind; it can never satisfy a required positive-path proof or promote outcome evidence.

The parent link and `receipt_sequence` form one append-only chain. Replay state is partitioned by workspace, holon, and authority domain; actor, session, and authority-level changes inside a live lease are rejected as binding mismatches. Genesis alone may use the zero parent. Every later receipt must name the exact prior signed receipt ID and advance the canonical decimal sequence by one. A renewal retains the lease ID, advances the generation and fence, and names the global chain head as its parent. The renewed receipt becomes the current lease-authorization root, which every later mutation receipt must name explicitly. Expiry and revocation terminate the lease. Mutation admission binds the current live generation and fence; exactly one terminal mutation receipt may consume that admission.

## Canonical signature and content address

The Ed25519 receipt signature is computed over these exact JCS bytes:

```text
JCS({
  domain: "AEGIS_CROSS_RUNTIME_RECEIPT_SIGNATURE_V1",
  schema_version,
  receipt_kind,
  receipt_body,
  proof: {
    algorithm,
    signer_key_id,
    verifier_identity_root,
    trust_registry_version,
    trust_registry_root
  }
})
```

The signature message excludes only `proof.signature` and `receipt_id`.

After the signature is attached, `receipt_id` is derived exactly as follows:

```text
SHA256(JCS({
  domain: "AEGIS_CROSS_RUNTIME_RECEIPT_ID_V1",
  envelope: {
    schema_version,
    receipt_kind,
    receipt_body,
    proof: {
      algorithm,
      signer_key_id,
      verifier_identity_root,
      trust_registry_version,
      trust_registry_root,
      signature
    }
  }
}))
```

Thus V1 `receipt_id` is also the signed envelope's content address. A store lookup by receipt ID and a lookup by content hash must resolve to the same exact bytes; any second byte sequence for the same key is corruption, not an update.

Domain separation is mandatory. An authority, outcome-certificate, event, trust-registry, or other signature is not interchangeable with a receipt signature even if its JSON fields happen to match.

## Explicit time and clock-skew model

`timestamp_ms`, `expires_at_ms`, registry times, and verifier observation time are canonical decimal strings representing epoch milliseconds. They are provided by the caller's trusted event or clock context. Receipt issuance, verification, replay, and tests must not call `Date.now()`, `time.time()`, or consult a model response for temporal authority.

The resolver receives `observed_at_ms` and `max_clock_skew_ms` separately from the untrusted receipt. It rejects receipts from beyond the allowed future skew, receipts or signing keys outside their validity interval, and mutation admission under an expired lease. At the live Python authority boundary, lease decisions use the later of the signed event timestamp and the separately supplied monotonic observation time. A backdated event timestamp therefore cannot revive an expired lease. Historical restart verification does not apply that lower bound retroactively; it verifies the signed event-time chain. Boundary equality and skew behavior are fixed by tests. A `LEASE_EXPIRED` receipt must be timestamped at or after its bound expiry. Clock ambiguity never extends a lease silently; failure to establish trusted time denies promotion.

## Trust-root registry

The exact top-level `Receipt Trust Registry V1` fields are:

```text
schema_version = "1.0.0"
registry_body
proof
registry_root
```

The exact `registry_body` fields are:

```text
registry_version
previous_registry_root
issued_at_ms
valid_from_ms
expires_at_ms
operator_key_id
keys
```

Every key entry contains exactly:

```text
key_id
public_key
verifier_identity_root
valid_from_ms
expires_at_ms
status = ACTIVE | REVOKED
authority_domains
receipt_kinds
```

The registry proof contains exactly `algorithm = "Ed25519"` and `signature`.

Registry signatures and roots use these exact derivations:

```text
signature_message = JCS({
  domain: "AEGIS_RECEIPT_TRUST_REGISTRY_SIGNATURE_V1",
  schema_version,
  registry_body,
  proof: { algorithm }
})

registry_root = SHA256(JCS({
  domain: "AEGIS_RECEIPT_TRUST_REGISTRY_ROOT_V1",
  registry: {
    schema_version,
    registry_body,
    proof: { algorithm, signature }
  }
}))
```

The signature message excludes `proof.signature` and `registry_root`; the root input excludes only `registry_root`.

Trust begins with an operator public key or registry root pinned outside all model output, receipt data, chat context, and fetched registry content. `operator_key_id` is a binding checked against that host context; it is not itself a trust root. Only the explicitly pinned genesis may use the zero previous root. Every rotation is an operator-signed successor with a strictly increasing canonical version and the exact previous registry root. Historical versions remain resolvable for historical verification, subject to the declared validity and revocation policy.

Key IDs and public keys are unique. Authority-domain and receipt-kind scopes are explicit and non-empty. The resolver rejects unknown registries or keys, broken registry chains, stale or rollback versions, invalid operator signatures, revoked keys, keys outside their interval, identity mismatches, and keys used outside their declared domain or receipt-kind scope. A receipt signer can never authorize its own trust-root rotation.

## Resolver and add-only persistence

The TypeScript resolver accepts a receipt ID or signed content hash plus a separately supplied trusted context. It retrieves the exact receipt, applies strict I-JSON and exact-schema validation, recomputes `receipt_id`, resolves and authenticates the registry chain against the pinned operator root, verifies the signer scope and Ed25519 signature, checks time, lease generation, fencing token, expected state, parent chain, and replay indexes, and returns a deeply immutable verified value.

Receipt and registry stores are add-only and content-addressed. Persisting the same bytes is idempotent; different bytes at an existing key fail closed. Each write is followed by exact read-back, closed-I-JSON normalization, and content-root verification. The trusted resolver then performs registry, signature, parent-chain, lease, fence, replay, and state verification before evidence can be promoted. A content-valid but untrusted orphan may be stored for forensics; it remains non-promotable. Process-local issuance sets are not evidence.

## Persistence-before-state and partial failure

Consequential mutation is a two-phase receipt protocol:

1. Validate authority, live lease, expected state, and replay indexes; persist and read back `MUTATION_ADMITTED` before contacting the provider or changing state.
2. After execution or denial, persist and read back exactly one terminal `MUTATION_COMPLETED`, `MUTATION_DENIED`, `MUTATION_CANCELLED`, or `MUTATION_FAILED` receipt before publishing a new canonical state root or allowing outcome-evidence promotion.

If admission persistence fails, no mutation may run. If the provider acts but terminal persistence or read-back fails, the canonical state root must not advance and the action is quarantined for operator reconciliation. An orphan admission is evidence of an incomplete attempt, never success. SQLite validates pending bytes inside the append transaction before commit. IndexedDB persists registry and receipt batches in one transaction; a late uniqueness violation aborts earlier writes in the same batch. Restart reconstruction must recover the receipt head, active lease, consumed admissions, terminal mutations, and replay indexes entirely from stored receipts and authenticated registries.

## Denial and failure state invariant

Every denied action has a resolvable signed terminal receipt and leaves canonical state unchanged:

```text
outcome == DENIED
before_state_root == after_state_root
canonical_state_root_after == canonical_state_root_before
```

Cancellation and terminal failure also require unchanged before and after roots unless a separately admitted, signed, and verified compensating mutation proves a rollback. A denial receipt is not permission to perform cleanup mutation. Tests must observe the canonical root before and after the denied provider boundary, not merely compare caller-supplied strings.

## Replay and concurrency

Receipt replay is distinct from read-only resolution. Re-resolving stored bytes is safe; attempting to admit or complete an already consumed mutation is rejected. A signed `MUTATION_DENIED` carrying `MUTATION_REPLAY` remains resolvable evidence of that rejected attempt and never becomes a second admission. The broad action-claim index binds actor, session, workspace, holon, authority domain, and action digest so a claimed action cannot be revived under a different lease or authority level. The signed attempt and terminal binding additionally fixes authority level, lease ID and generation, fencing token, nonce, authority root, lease-authorization root, parent, and receipt ID. Conflicting reuse of any unique operation binding is denied.

Concurrent acquisition, renewal, admission, completion, cancellation, or failure races are serialized at the persistent chain head. At most one contender can advance a given parent, generation, fence, or mutation admission. Contention evaluated before append produces a signed denial. A compare-and-append loser detected at the storage boundary receives a fail-closed persistence conflict and must recover the committed head before retrying; it cannot create a second receipt or terminal success. Storage conflicts are not reinterpreted as signed semantic decisions.

## Cross-runtime golden vectors

Golden inputs are closed I-JSON values with fixed RFC 8032 keys, decimal time, nonce, state roots, and lifecycle ordering. Python and TypeScript generate their outputs independently; neither generator invokes the other or consumes the other runtime's output. Each generator emits the same canonical 15-receipt chain covering all 11 V1 receipt kinds. Generated files contain the complete registry, receipts, terminal receipt ID, trusted replay context, receipt IDs, registry root, and signatures.

TypeScript must independently verify the Python-generated registry and every Python-generated receipt kind. Python must independently verify the TypeScript-generated registry and every TypeScript-generated receipt kind. Matching inputs must produce byte-identical signing messages, deterministic Ed25519 signatures, receipt IDs, and registry roots. Tampered vectors are rejected. Generators write to temporary paths during verification so tests do not mutate committed evidence.

## Migration

Existing `AuthorityDecisionReceipt` signatures remain authorization evidence under their existing policy. Existing unsigned `LeaseReceipt`, `MutationReceipt`, and their in-memory issuance sets are legacy T2-only evidence. They are not grandfathered, wrapped, re-signed, or reinterpreted as V1 cross-runtime receipts. Evidence containing only legacy terminal roots remains recordable as historical or negative evidence but cannot promote authoritative provenance.

New activity uses the cross-runtime envelope from lease issuance onward. A chain cannot mix legacy and V1 parents. Migration starts a declared V1 genesis bound to the current canonical state, workspace, actor, session, holon, authority, and pinned trust registry.

## Advisory outcome boundary

Independent receipt verification proves signature, signer scope, chain, lease, time, action, and state bindings. It does not prove that an adaptation is beneficial or safe. `outcome-comparator.ts` remains advisory: it cannot execute or revert a mutation, grant authority, alter canonical state, or update competence. Authenticated denial and failure evidence may be persisted as negative evidence without becoming authority.

## Projection prohibition and admission condition

No cockpit, MCP, game, or other product projection may label receipt provenance authoritative until all of the following pass together:

1. Python-generated receipts verify independently in TypeScript.
2. TypeScript-generated verification decisions replay without private chat context.
3. Every success and denial resolves to a signed terminal receipt.
4. Unsigned, unknown-root, expired, stale-fence, stale-state, broken-chain, replayed, ambiguous-identity, malformed, and partially persisted evidence cannot promote.
5. Denial state-root preservation is observed.
6. Restart and exact read-back verification pass for every receipt kind and registry rotation.
7. The complete existing Python and TypeScript suites, typecheck, production build, browser bundle, frozen hashes, and diff checks remain clean.

Until that admission condition is recorded, the schemas and implementation are proposed infrastructure, not an authoritative cockpit or MCP claim.

## Consequences and remaining integration blockers

This design removes private process memory and chat history from receipt verification, makes signer rotation explicit, and turns receipt identity into a stable cross-runtime content address. It also requires durable receipt and registry transport, trusted caller time, operator key provisioning, atomic chain-head coordination, and complete lifecycle evidence.

After this phase passes, cockpit or MCP integration still requires a confined read-only transport, an explicit freshness source for the pinned registry and clock observation, operator-visible degraded states, and UI wording that distinguishes verified provenance from an advisory outcome assessment. Those integrations are outside this ADR's implementation slice.
