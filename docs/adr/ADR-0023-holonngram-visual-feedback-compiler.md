# ADR-0023: Holonñgram visual feedback compiler

Status: Accepted for projection-only implementation; live projection admission pending

Depends on: ADR-0021, ADR-0022

## Context

AEGIS already has formulas, runtime traces, state roots, signed lifecycle
receipts, and a read-only Studio. It lacked one closed visual grammar that turns
those objects into an inspectable state-transition surface without allowing the
surface to become an authority source.

Static mathematical notation is insufficient for this role. The projection
must show the pressure produced by a formula: the receipt-backed transition,
expected and observed roots, terminal outcome, feedback signal, measured edge
changes, next-route suggestion, and chain horizon. At the same time, a visual
frame must never manufacture changed fields, scores, receipt beads, or
provenance that its verified source does not contain.

## Decision

The normative wire contract is
`schemas/holonngram-visual-feedback.v1.schema.json`. The TypeScript compiler is
`sovereign-omega-v2/src/projection/holonngram-compiler.ts`.

Protocol identifiers use the ASCII spelling `holonngram`. Product copy may use
the name “Holonñgram.”

The compiler accepts only:

1. a terminal receipt ID;
2. a separately supplied trusted receipt-resolution context;
3. a content-addressed receipt/trust-registry source; and
4. a closed I-JSON formula projection observation.

It invokes `resolveAndVerifyCrossRuntimeReceiptChainV1`, then reads the terminal
receipt back from the same content-addressed source. It recomputes the terminal
receipt ID and binds its kind, outcome, identities, authority, lease, fence,
action, state roots, and result to the resolver decision. A malformed,
unresolvable, unsigned, unknown-root, stale, replayed, or mismatched source
produces no frame.

A caller-supplied verification decision is not a compiler input. A valid
`decision_digest` proves decision self-consistency, not fresh receipt-chain
resolution.

## Canonical frame

The exact top-level fields are:

```text
schema_version = "1.0.0"
artifact_kind = "AEGIS_HOLONNGRAM_VISUAL_FEEDBACK_V1"
compiler_version = "holonngram-compiler-v1"
topology_id = "HOLONNGRAM_19_V1"
epistemic_status = "DERIVED_NON_AUTHORITATIVE"
source
formula_trace
state_comparison
feedback
visual
safety
frame_digest
```

`source` copies the verified decision bindings and the authenticated terminal
receipt fields needed by the visual grammar:

```text
provenance_status
decision_digest
terminal_receipt_id
terminal_receipt_kind
terminal_outcome
chain_digest
receipt_count
registry_roots
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
terminal_timestamp_ms
terminal_nonce
denial_codes
verifier_identity_root
observed_at_ms
max_clock_skew_ms
```

`formula_trace` contains the caller-supplied formula ID, version, definition
digest, transition ID, content-derived projection trace ID, formula
input/output digests, execution status, and measurement status. This slice does
not resolve a signed or content-addressed formula execution artifact. It
therefore emits only `NOT_EXECUTED` or `UNVERIFIED_CALLER_INPUT`; it never
claims that a formula executed successfully. Formula hashes use separate
domains:

```text
input_digest =
  SHA256(JCS({
    domain: "AEGIS_HOLONNGRAM_FORMULA_INPUT_V1",
    source
  }))

output_digest =
  SHA256(JCS({
    domain: "AEGIS_HOLONNGRAM_FORMULA_OUTPUT_V1",
    state_comparison,
    feedback,
    edge_updates,
    next_route
  }))

trace_id =
  SHA256(JCS({
    domain: "AEGIS_HOLONNGRAM_FORMULA_TRACE_V1",
    formula_id,
    formula_version,
    formula_definition_digest,
    input_digest,
    output_digest
  }))
```

The frame content address is:

```text
frame_digest =
  SHA256(JCS({
    domain: "AEGIS_HOLONNGRAM_VISUAL_FEEDBACK_FRAME_V1",
    frame: <all frame fields except frame_digest>
  }))
```

All serialization uses the existing strict I-JSON boundary and the repository's
sole RFC 8785 JCS encoder. No visual-feedback serializer is introduced.

## State comparison and feedback

State comparison is roots-only. It carries authenticated observed, expected,
before, and after roots and labels field-level status `ROOTS_ONLY`. A hash
difference cannot prove which fields changed, so `changed_fields` is
intentionally absent.

Only `MUTATION_COMPLETED` may produce `STATE_CHANGED`. Denied, cancelled,
failed, expired, and revoked terminals must preserve
`before_state_root == after_state_root`. The deterministic feedback map is:

| Terminal | Signal | Severity | Boundary |
|---|---|---|---|
| Mutation completed | `REINFORCE` | `INFO` | `NONE` |
| Mutation cancelled | `ROLLBACK` | `WARNING` | `CANCELLATION` |
| Mutation failed | `ROLLBACK` | `CRITICAL` | `EXECUTION` |
| Lease expired/revoked | `FAIL_CLOSED` | `CRITICAL` | `LEASE` |
| Denial | versioned denial-code classification | at least `WARNING` | classified boundary |

Unknown denial codes fall back to `NEEDS_REVIEW`; they never produce a more
permissive signal. When a denial contains codes from multiple categories, the
compiler selects the strongest fail-closed category before any repair or review
category. Equal critical categories use the versioned deterministic order
`TRUST`, `FENCING`, `LEASE`, then `REPLAY`.

Scores and edge deltas are canonical fixed-point decimal strings in parts per
million, bounded to ±1,000,000. Caller-provided values are explicitly labelled
`CALLER_SUPPLIED_UNVERIFIED`; hashing them gives deterministic integrity, not
formula-execution provenance. If no formula measurement exists, the status is
`NOT_COMPUTED`, values are `null`, and edge updates are empty. The compiler
does not invent a zero score. A future trace-backed measurement status requires
a separately resolvable formula execution artifact and trust rule.

## Fixed topology

`HOLONNGRAM_19_V1` has one center node, six inner roles, and twelve outer
witnesses:

```text
C0  CURRENT_ENVELOPE
I1  INTERPRETER
I2  ASSESSOR
I3  LEASE_GUARD
I4  EXECUTOR
I5  VERIFIER
I6  COMMITTER
O1  ACTOR_WITNESS
O2  SESSION_WITNESS
O3  WORKSPACE_WITNESS
O4  HOLON_WITNESS
O5  AUTHORITY_WITNESS
O6  LEASE_WITNESS
O7  FENCE_WITNESS
O8  EXPECTED_STATE_WITNESS
O9  OBSERVED_STATE_WITNESS
O10 ACTION_WITNESS
O11 RESULT_WITNESS
O12 TRUST_CHAIN_WITNESS
```

Node order, ring, role, state, and content-addressed source references are
validated on compilation and integrity read-back. Where a signed lease
lifecycle field legitimately uses the protocol's zero sentinel, its visual
node references the non-zero terminal receipt ID instead of presenting the
sentinel as evidence. A receipt timeline contains only the terminal receipt ID,
chain digest, and receipt count because the current resolver decision does not
expose the ordered receipt IDs. The compiler does not fabricate intermediate
ledger beads.

## Non-authority invariant

Every frame contains:

```text
safety.grants_authority = false
safety.executes_mutation = false
safety.promotes_evidence = false
safety.claims_authoritative_provenance = false
safety.route_adjustment_authorized = false
```

The source may truthfully say that receipt provenance was verified. The visual
artifact itself remains derived and non-authoritative. `next_route` is a display
suggestion, never an executable route decision.

## Studio boundary

The first Studio Holonñgram surface implements the seven requested visual
regions and the 19-node layout, but it is intentionally not connected to the
receipt resolver. Bridge telemetry is labelled unverified display input.
Formula IDs, roots, receipts, trust, and edge measurements remain visibly
unresolved. This gives operators an inspectable grammar without weakening
ADR-0022's projection prohibition.

`verifyHolonngramVisualFeedbackFrameIntegrityV1` validates strict shape and
attacker-detecting consistency only when the expected digest is already
trusted; because an untrusted party can recompute an unsigned frame digest, the
function does not authenticate receipt provenance. Live binding requires a
confined read-only transport that delivers a
`HolonngramVisualFeedbackFrameV1` and invokes
`resolveAndCompileHolonngramVisualFeedbackV1` again against current
operator-pinned trust and time context. Cockpit, MCP, game, provider mutation,
and route actuation remain out of scope.
