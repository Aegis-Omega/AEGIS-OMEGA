# AEGIS Client Authority Model

**Status: Draft**
**Epistemic tier: T2 (normalization of existing T0–T2 primitives — no new schema)**

This document is a normalization layer over primitives that already exist in the
monorepo. Every concept below cites the code that implements it. Nothing here
invents a new envelope, registry, verdict vocabulary, or chain. Where a concept
is not yet built, it is explicitly marked as the Phase 2 gap (§7) — everything
else is a name for something already running.

---

## 1. Authority Boundaries

Clients express intent; the runtime decides. There are no client-specific
authority paths — a Swift app and a shell script hit the same validation,
the same tier gate, and the same constitutional audit.

Known clients:

| Client | Location |
|---|---|
| Swift (iOS edge) | `clients/gemma-edge-ios/` (Swift package: `Package.swift`, `Sources/`, `Tests/`) |
| Go adapter | `clients/go/client.go` |
| Python adapter | `clients/python/` |
| Sheets adapter | `clients/sheets/` |
| Shell adapter | `clients/shell/` |
| CLI | `packages/aegis-py/aegis/cli.py` (`aegis` command; sync/async clients in `client.py`, `async_client.py`) |
| Web / agents | any HTTP caller of the `/platform/*` surface |

No client carries authority. Authority lives server-side in the bridge
(`sovereign-omega-v2/python/bridge.py`) and the TypeScript governance runtime
(`sovereign-omega-v2/src/`).

## 2. Intent Envelope — the existing two-layer reality

There are exactly two intent layers, both already implemented:

1. **At the client boundary** the intent envelope IS `CollaborationRequest`
   (`packages/shared/lib/platform-contract.ts:83-94`): objective, mode, live,
   plus optional generation / memory_context / autonomous / max_agents. It is
   validated by `validate_collaboration_request`
   (`sovereign-omega-v2/python/platform_helpers.py:671-700`) and sanitized at
   the ingestion boundary by `sanitize_objective`
   (`platform_helpers.py:92-113`, injection markers + length cap).
2. **Inside the membrane** intent reduces to `EventEnvelope`
   (`sovereign-omega-v2/src/core/types.ts:131-145`): hash-chained
   (`prev_hash`/`self_hash`), sequence-numbered, producer-attributed. The Law
   of Silence: agents communicate exclusively through mediated `EventEnvelope`.

**No third envelope may be created.** The Law of Silence is exclusive — any
new "client intent" object must reduce to `CollaborationRequest` at the
boundary or `EventEnvelope` inside the membrane, or it does not exist.

## 3. Capability Registry — a read-projection, not a store

Client-facing capability is a projection of existing gates, never a new
authority store:

- **Tier gates**: `validate_tier_capabilities`
  (`platform_helpers.py:40-62`) — `live=True` and advanced modes require
  operator/sovereign; called after key verification, before swarm execution.
- **Tool catalog**: `GET /platform/tools` returns `AgentTool` entries with
  `tier_required: 'explorer' | 'operator' | 'sovereign'`
  (`platform-contract.ts:235-245`); raw credentials are never returned.

Internal reference semantics (what "capability" means inside the runtime):

- `CapabilityGuard` (`src/environment/kernel/capability_guard.ts:24-92`) —
  register (T0–T2 provenance + bounded entropy + ontology term required,
  :31-52), grant (least-privilege scoped, :54-80), revoke.
- `CapsuleManifest` (`src/capsule/types.ts:29-55`) — the four admissible
  capsule capability types (READ_STATE / EMIT_EVENT / QUERY_TOPOLOGY /
  OBSERVE_LINEAGE) plus entropy budget.
- Plugin contracts: `createContract`
  (`src/extensions/contracts/contract.ts:10-32`) — least-privilege grants
  with a mandatory admissibility reason.

**Capability mutation has exactly one path**: proposal → verdict →
AdaptiveLineage → martingale. `buildProposal`/`assessProposal`
(`src/capsule/evolution.ts:21-119`) produce an `EvolutionResult`; the verdict
enters the hash-linked `AdaptiveLineageEntry` chain
(`src/frame/adaptive-lineage.ts:21-32`); adaptation stays bounded by
`certifyMartingale` / `assertMartingaleAnchored`
(`src/constitutional/martingale.ts:57`, `:104`). A parallel mutation
authority is a prohibited construct — T0_ABORT: autonomous mutation
authority.

## 4. Policy Decision — the existing verdict shape

Every decision already reduces to `{verdict, reason, result_hash}` (see
`AdmissibilityResult`, `src/constitutional/reduction.ts:64-70`, and
`EvolutionResult`, `src/capsule/evolution.ts:32-38`). Four verdict
vocabularies exist; the rule is **no fifth vocabulary**:

| Vocabulary | Values | Where | Scope |
|---|---|---|---|
| Admissibility | `ADMITTED` / `REJECTED` | `src/constitutional/reduction.ts:62-70` | ontology abstraction admission |
| Evolution | `APPROVED` / `REJECTED` | `src/capsule/evolution.ts:19,32-38` | capability proposals |
| Constitutional audit | `APPROVED` / `FLAG` / `QUARANTINE` | `packages/shared/lib/platform-contract.ts:130-135` | the WIRED client-facing verdict |
| Mutation gate | `PENDING` / `APPROVED` / `REJECTED` | `sovereign-omega-v2/python/gate.py:81-88` (FROZEN) | proposal quorum; unknown = PENDING, never assumed approved |

Clients only ever see the third vocabulary. The others are internal and must
not leak onto the platform surface.

## 5. Evidence Envelope = ExecutionEnvelope

The evidence envelope already exists: the float-free, hash-chained
`ExecutionEnvelope` (`sovereign-omega-v2/python/canonical_envelope.py`,
`EnvelopeChain` :79-116; float policy in
`docs/adr/0001-envelope-float-encoding.md`). It is dual-emitted on the WIRED
path in `bridge.py` — the `/claude` handler and
`_platform_run_collaboration` both attach `envelope` alongside the
byte-identical legacy hashes.

Field disambiguation (the reason for the 2026-07 rename): the body field
`epistemic_tier` (`canonical_envelope.py:103`) holds the epistemic T-tier of
the call ('T1'/'T2') and is DISTINCT from customer `tier` — the plan
(`explorer` / `operator` / `sovereign`) returned by `verify_api_key`
(`platform_helpers.py:304`) and typed in `PlatformStatusUsage.tier`
(`platform-contract.ts:170-176`).

The `signature` slot is reserved and currently `None`
(`canonical_envelope.py:111`) — Phase 2 fills it with a Cloud KMS Ed25519
signature over `envelope_hash`.

## 6. Replay Reference — a named tuple, no new chain

A replay reference is the tuple
`(execution_id, envelope_hash | chain_terminal_hash, seq)` — every component
is already served:

- `execution_id`: on every response via `PlatformEnvelope`
  (`platform-contract.ts:19-25`) and retrievable via
  `GET /platform/executions/{id}` (`ExecutionGetResult`,
  `platform-contract.ts:149-154`).
- `envelope_hash` / `seq`: in the dual-emitted `ExecutionEnvelope` (§5).
- `chain_terminal_hash`: in `ComplianceExport`
  (`platform-contract.ts:198`).

No new chain is introduced; replay resolution composes what is served today.

## 7. Client identity → provenance binding (THE ONLY NEW BUILD — Phase 2)

The one genuine gap. Today `verify_api_key`
(`platform_helpers.py:249-304`) authenticates a principal (atomic
verify-and-increment against Supabase, returns `(customer_email, tier)`), but
that identity never enters a hash chain:

- Execution ownership is a mutable in-memory dict — the bridge updates
  `_executions[execution_id]` in place so the `email` ownership tag survives
  (`bridge.py:371-376`) — auditable by nobody after process death.
- `EventEnvelope.producer_id` (`src/core/types.ts:137`) exists in the type
  but is exercised only by tests and internal event stores; no client
  identity flows into it on the WIRED platform path.

Phase 2 adds `(principal_digest, capability_grant_ref)` into the signed
envelope body, alongside the KMS Ed25519 signature of §5. That is the entire
build; every other section of this document is naming, not construction.

## 8. Conformance

All clients speak the contract-version-rejected protocol: the bridge stamps
`X-Contract-Version` on responses (`bridge.py:1635`), and clients hard-fail
on mismatch — e.g. the Go adapter rejects any `contract_version != "1.0.0"`
and any `is_replay_reconstructable != true` (`clients/go/client.go:67-68`).

Canonicalization conformance is the cross-language digest gate: every
implementation must reproduce the frozen vectors in
`test/vectors/canon-vectors.json` (TS: `test/unit/canon-equivalence.test.ts`;
Python: `python/tests/test_canon_equivalence.py`). Per-client verification
follows the proven rechain pattern in
`verifiable/cross_language/verify.sh` (fixture → per-language rechain →
digest comparison, stages pinned in `stages.json`).

## 9. Epistemic status

This document is a T2 normalization of existing T0–T2 primitives. Its
concepts should be registered through the existing ontology admission path,
`admitAbstraction` (`src/constitutional/reduction.ts:114`), which
mechanically enforces exactly what this document promises: every abstraction
must carry primitive/replay/topology mappings (`OntologyInput`,
`reduction.ts:78-85`), T4/T5 tiers are blocked, and duplicate names are
rejected — i.e. a second "client authority model" cannot be admitted beside
this one.
