# Replay Constitution
## Epistemic Tier: T0
## Status: Constitutional Law — immutable without /guardian APPROVED verdict

Replay is constitutional infrastructure. It is not debugging infrastructure.
The append-only event substrate (E3) is the system's source of truth.
All governance decisions must be reconstructable from it.

---

## Constitutional Laws

### LAW-01 — Historical Replay Produces Identical Invariant Outcomes
Historical replay of the same event sequence must produce identical invariant check
results across any two conforming deployments.

**Engineering requirement:**
- Deterministic event ordering (sequence numbers are the authority — never wall-clock time)
- Canonical serialization: RFC 8785 JCS for TypeScript events; Q16.16 fixed-point for
  Python Layer B metrics; little-endian for Rust substrate
- Version-pinned computation: `RuntimeVersionPin` must match at replay time or abort

**Violation consequence:** T0_ABORT — replay infrastructure is compromised.

**Implementation:** `invariant-checker.ts:checkInvariants()` + `replay.rs:verify_structural()`

---

### LAW-02 — Archive Version Boundaries Are Explicit and Machine-Readable
Every replay archive must declare its schema version in a machine-readable header.
Deserializers must read the version before any other field.
Version-blind deserialization is a constitutional violation.

**Engineering requirement:**
- `ArchiveVersion` wire format: 6 bytes (major:u16, minor:u16, patch:u16), little-endian
- `ArchiveHeader` must be the first 118 bytes of every archive
- `CycleArchive.schema_version` is the TypeScript-layer version stamp
- `CYCLE_ARCHIVE_SCHEMA_VERSION = '1.0.0'` is the canonical constant

**Violation consequence:** Deserialization panic (constitutional; prevents silent corruption).

**Implementation:** `archive.rs:ArchiveVersion` + `types.ts:CYCLE_ARCHIVE_SCHEMA_VERSION`

---

### LAW-03 — Replay Decoding Compatibility Is Mandatory Across Deprecated Schemas
A deprecated serialization schema must remain decodable until a major version boundary
is explicitly declared. Minor and patch version increments are backward-compatible by law.
Archives produced under v1.x.x must be decodable by any v1 reader regardless of minor version.

**Engineering requirement:**
- Same-major compatibility check: `reader_version.is_compatible_with(archive_version)`
- from_bytes implementations must handle all valid v1.x wire formats
- Deprecated fields: zero-padded reserved bytes in wire format (not removed)
- Documentation: deprecated field positions remain fixed even when semantically unused

**Violation consequence:** T1_ALERT; operator must provide a migration path before proceeding.

**Implementation:** `archive.rs:ArchiveVersion::is_compatible_with()`

---

### LAW-04 — No Nondeterministic Entropy Source May Influence Replay Reconstruction
Replay reconstruction may not depend on:
- Wall-clock time (`Date.now()`, `time.time()`, `SystemTime::now()`)
- Random number generation
- OS-specific behavior (file ordering, hash map iteration)
- Thermal state (GPU temperature readings are physical observables — see TELEMETRY_SPEC.md §tgcs_variance)
- Network responses or external API calls

Only the event sequence and version pins are valid inputs to replay reconstruction.

**Engineering requirement:**
- `no_std`-compatible replay primitives in `constitutional-substrate`
- All sequence-derived timestamps (not wall-clock) in event envelopes
- Python Layer B: sequence numbers used instead of `time.time()` in deterministic paths
- Exception registry: physical observables (thermal, disk I/O) are annotated in TELEMETRY_SPEC.md
  as non-reconstructable — their archived values are historical annotations only

**Violation consequence:** T0_ABORT on any Date.now() call outside `src/event/uuid.ts`

**Implementation:** `core-invariants.md` + `typescript.md` rules

---

### LAW-05 — Governance Decisions Must Be Reconstructable from Replay Archives
Every gate decision (ACCEPTED/REJECTED), every invariant check result, and every
Ralph cycle outcome must be reconstructable from the CycleArchive and event stream.
A governance decision with no replay path is constitutionally inadmissible.

**Engineering requirement:**
- `CycleArchive` contains full `RalphCycle` records including `gate_result`
- `GateDecisionPayload` is an event payload in the E3 substrate (GATE_EVALUATED event)
- `InvariantViolation` records must appear in the event stream when violations occur
- `VerifierAttestation` is replay-storable via `attestation.rs::VerifierAttestation::to_bytes()`

**Violation consequence:** T1_ALERT; governance audit trail is incomplete.

**Implementation:** `ralph-loop.ts:exportArchive()` + `store.ts:append()`

---

### LAW-06 — Invariant Violations During Replay Must Halt Admissibility Validation
When replaying a historical archive for audit purposes, any invariant violation discovered
in the historical record must halt the admissibility validation of that archive segment.
The violation is logged, the archive segment is flagged, and operator review is required.

**Engineering requirement:**
- `invariant-checker.ts:checkInvariants()` applied at each replayed event
- `hasT0Violation(result)` → halt replay validation, flag segment as `INADMISSIBLE`
- T1 violations → continue replay but annotate segment as `DEGRADED`
- Replay halt is not a system halt — the live runtime continues; only the audit path halts

**Violation consequence:** Replayed archive segment marked `INADMISSIBLE`. Governance
decisions from that segment require manual review before they may be cited as precedent.

**Implementation:** `invariant-checker.ts:checkInvariants()` + `replay.rs:verify_structural()`

---

### LAW-07 — Replay Artifacts Are Append-Only Constitutional Records
Events may not be deleted, modified, or reordered in the event substrate.
The E3 event store is an append-only ledger. TOMBSTONE operations mark payloads as
destroyed but preserve the event envelope (including hash chain linkage).
The `ReplayLedger` enforces this at the substrate level: no remove, no update.

**Engineering requirement:**
- `ReplayLedger` exposes only `append()` and `verify_structural()` on the public API
- `EventStore.append()` is the only write path — no `update()`, no `delete()`
- Tombstone events (`TOMBSTONE_CREATED`) preserve the envelope; only payload is zeroed
- `ReplayLedger::from_events()` is test-only and must not be exposed in production builds

**Violation consequence:** T0_ABORT — the append-only invariant is constitutional bedrock.

**Implementation:** `replay.rs:ReplayLedger` + `event/store.ts`

---

## Serialization Canon

These decisions are constitutionally irreversible once replay archives accumulate.

| Concern | Decision | Rationale |
|---------|----------|-----------|
| Byte order | Little-endian throughout | Architecture-independent; matches x86 native |
| Integer sizes | Explicit widths (u16/u32/u64/i64) | No implicit platform-dependent sizes |
| Boolean encoding | `0x00` = false, `0x01` = true, other bytes = invalid | No interpretation ambiguity |
| String encoding | UTF-8, zero-padded to field width | Deterministic; no null-terminator ambiguity |
| Fixed-point | Q16.16 (i64, shift=16) | Matches Python `INT_SHIFT=16`; cross-language determinism |
| Hash function | SHA-256 (integration boundary) | Substrate stores hashes; callers compute |
| JSON canonical form | RFC 8785 JCS (TypeScript layer) | Cryptographic integrity for event envelopes |
| Floating-point | **PROHIBITED** | Cross-architecture non-determinism |

---

## Replay Integrity Attestation

An archive is constitutionally attested when:

1. `ArchiveHeader.integrity_hash` matches SHA-256 of the cycle payload bytes
2. `ArchiveVersion` is compatible with the current reader version (LAW-02)
3. All events pass `verify_structural()` (LAW-01)
4. No T0 invariant violations are present in the historical record (LAW-06)
5. All governance decisions have corresponding event envelopes (LAW-05)

An archive that satisfies all five conditions is `ATTESTED`.
An archive that fails any condition is `INADMISSIBLE` until a guardian review resolves
the specific failure mode.

---

## Amendment Process

Changes to this document require:
1. `/guardian APPROVED` verdict from the constitutional authority
2. A new entry in the Evolution History table below
3. All downstream implementations updated in the same commit
4. Gate 8 (215 tests) still passing after the amendment

## Evolution History

| Law | Date | Amendment | Authority |
|-----|------|-----------|-----------|
| LAW-01..07 | 2026-05-19 | Initial constitutional codification | ChatGPT adversarial audit CONFIDENCE 0.98 |
