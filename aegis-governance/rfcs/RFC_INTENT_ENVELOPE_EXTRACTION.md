# RFC: Intent Envelope Extraction & Environment Canonicalizer Spec

**Status:** DRAFT  
**Area:** Authority Plane / Ingestion Layer

## 1. Purpose and Scope

The **Intent Envelope** is the canonical, non-authorizing boundary object that
captures and converts raw external client requests into an immutable, verifiable
runtime input for the AEGIS Authority Plane.

By formalizing this ingestion boundary, AEGIS guarantees that no un-vetted client
parameters or out-of-band execution variables drift into the downstream pipeline
unnoticed. This RFC freezes the behavior of the `EnvironmentCanonicalizer`,
clarifies edge-extraction rules, and locks the structural JSON schema required
before building individual client adapters such as Swift, CLI, and Web.

---

## 2. EnvironmentCanonicalizer Invariants

The `EnvironmentCanonicalizer` operates under a zero-trust model for system
execution space. It must adhere to the following behavioral rules:

- **Measurement only:** The canonicalizer is strictly read-only. It must never
  mutate the active runtime `PATH` or any local process state. Its sole output is
  a deterministic measurement signature: `environment_hash`.
- **Separation of concerns:** Canonicalization occurs strictly as a passive
  observation pass. Transformed strings or sorted environment variables must
  never be injected back into the active shell execution context.
- **Three-state classification taxonomy:** Every incoming environment variable
  key must be filtered through a strict registry with three categories:
  - `UNKNOWN`: The variable is unregistered. It is excluded from the hash
    computation by default, triggers an immediate audit warning, and must be
    explicitly registered before production promotion.
  - `KNOWN_EPHEMERAL`: The variable is recognized as transient or volatile, such
    as `PID`, `TIMESTAMP`, or `RANDOM_SEED`. It is tracked for debugging logs but
    skipped during deterministic hash compilation.
  - `KNOWN_DETERMINISTIC`: The variable is explicitly verified as a structural
    element of the execution footprint, such as `PYTHONPATH`, `NODE_ENV`, or
    `COMPILER_VERSION`. It is formatted and included in the hash.
- **Audit on exclusion:** Every excluded or omitted variable must produce an
  isolated, structured audit line with `{ field_name, reason, timestamp,
  request_id }`.
- **Canonicalization scope:** Isolation is restricted to identification and
  validation parameters, including `actor_identity`, `client_identity`, and
  static configuration arrays. Running operational components, open file
  descriptors, active network sockets, and ephemeral memory caches must never
  enter canonicalizer boundaries.
- **Hashing determinism:** The final serialization format enforces deterministic
  ASCII sorting, alphabetical key ordering, whitespace stripping, and an explicit
  hashing function defaulting to `sha256`. The algorithm identifier must
  accompany the hash text string.
- **Immutable tracking linkage:** The derived `environment_hash` and its
  classification metadata are committed immediately to both the `IntentEnvelope`
  and the resulting downstream `EvidenceEnvelope`.

---

## 3. Extraction Layer Responsibilities

```text
[ Client Payload / Raw Input ]
              │
              ▼
┌───────────────────┐
│  Extraction Layer │ ──► ONLY: collect context, normalize, commit hash
└─────────┬─────────┘
          │
          ▼
[ IntentEnvelope ]   ──► MUST NOT: authorize, select capabilities, run tools
```

### The Extraction Layer Must

1. Gather contextual footprints including active environment maps, calling client
   headers, and host session tokens.
2. Clean and normalize data footprints using deterministic serialization layers.
3. Commit state securely by building and signing the structural payload hash:
   `input_commitment`.

### The Extraction Layer Must Not

- Make policy assertions or parse capability access decisions.
- Dynamically match or attach operational capability models.
- Execute tools, instantiate system tasks, or mutate process environments.

---

## 4. IntentEnvelope JSON Schema Specification

```json
{
  "$id": "https://aegis.example/schemas/IntentEnvelope.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "IntentEnvelope",
  "type": "object",
  "required": [
    "request_id",
    "actor_identity",
    "client_identity",
    "capability_requested",
    "input_commitment",
    "policy_context",
    "timestamp",
    "attestation",
    "environment_hash"
  ],
  "properties": {
    "request_id": {
      "type": "string",
      "format": "uuid"
    },
    "actor_identity": {
      "type": "object",
      "required": ["actor_id", "identity_hash"],
      "properties": {
        "actor_id": { "type": "string" },
        "identity_hash": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" }
      },
      "additionalProperties": false
    },
    "client_identity": {
      "type": "object",
      "required": ["client_id", "client_hash"],
      "properties": {
        "client_id": { "type": "string" },
        "client_hash": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" }
      },
      "additionalProperties": false
    },
    "capability_requested": {
      "type": "object",
      "required": ["capability_id", "capability_version"],
      "properties": {
        "capability_id": { "type": "string" },
        "capability_version": { "type": "string" }
      },
      "additionalProperties": false
    },
    "input_commitment": {
      "type": "object",
      "required": ["canonical_serialization", "hash", "hash_algorithm"],
      "properties": {
        "canonical_serialization": { "type": "string" },
        "hash": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" },
        "hash_algorithm": { "type": "string" }
      },
      "additionalProperties": false
    },
    "policy_context": {
      "type": "object",
      "required": ["policy_ids", "policy_hashes"],
      "properties": {
        "policy_ids": { "type": "array", "items": { "type": "string" } },
        "policy_hashes": {
          "type": "array",
          "items": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" }
        }
      },
      "additionalProperties": false
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "attestation": {
      "type": "object",
      "required": ["attestor", "signature", "signature_algorithm"],
      "properties": {
        "attestor": { "type": "string" },
        "signature": { "type": "string" },
        "signature_algorithm": { "type": "string" }
      },
      "additionalProperties": false
    },
    "environment_hash": {
      "type": "object",
      "required": ["hash", "algorithm", "excluded_fields"],
      "properties": {
        "hash": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" },
        "algorithm": { "type": "string", "enum": ["sha256"] },
        "excluded_fields": {
          "type": "array",
          "items": { "type": "string" }
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

---

## 5. Canonical Serialization Implementation Rules

- **JSON determinism:** Payload serialization must enforce strict alphanumeric
  key sorting, UTF-8 encoding, removal of arbitrary whitespace formatting, and
  uniform serialization of numeric strings.
- **Temporal normalization:** Localized dates and times must be converted to
  ISO-8601 UTC at ingestion.
- **Primitive constraints:** Booleans and null representations must be coerced to
  native primitive states: `true`, `false`, and `null`. Mixed string booleans or
  type-falsy placeholders are not permitted.

---

## 6. Validation Invariants

An execution envelope is valid if and only if all of the following evaluations
pass:

- The incoming `actor_identity` object matches a known configuration, and its
  `identity_hash` resolves accurately.
- The `client_identity` accurately asserts root data ownership and maps to signed
  verification hashes.
- The requested target capability is fully specified with explicit identifiers
  and version tracks.
- The compiled `input_commitment` balances structural schemas against verifiable
  hash sequences.
- The execution timestamp is normalized and stays inside permissible system clock
  skew limits.
- The cryptographically bound payload attestation verifies against trusted
  execution keys or authenticated token proxies.

Any violation, parsing break, signature mismatch, or tracking identifier mutation
triggers immediate operational denial and appends tracking anomalies to the
system security logs.
