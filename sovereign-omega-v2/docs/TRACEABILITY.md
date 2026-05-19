# AEGIS Sovereign-Omega — Build Traceability Matrix

## Purpose

Records the epistemic provenance of every layer in the sovereignty runtime.
Each layer maps its modules to their tier classification, gate dependency,
and architectural role in the holonic hierarchy.

---

## Layer A — Core Substrate (Gates 1–3)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/core/canonicalize.ts` | T0 | 1 | RFC 8785 JCS canonical serialization |
| `src/core/types.ts` | T0 | 1 | Branded primitives, EventType, holonic enums |
| `src/core/immutable.ts` | T0 | 3 | deepFreeze, assertFrozen, withImmutableBoundary |
| `src/core/invariant-checker.ts` | T0 | 3 | INV-01..10 runtime invariant verification |
| `src/core/ralph-loop.ts` | T1 | 3 | R→A→L→P→H iterative governance cycle |
| `src/event/uuid.ts` | T0 | 2 | UUIDv7 generation (only permitted Date.now() call) |
| `src/event/store.ts` | T0 | 2 | IndexedDBSequenceAllocator — atomic sequence assignment |
| `src/event/workflow.ts` | T1 | 2 | E5 cognitive workflow payload schemas |

---

## Layer B — Calibration & Projection (Gates 4–5)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/calibration/vcg.ts` | T1 | 5 | VCG tracker — Bayesian calibration error metric |
| `src/projection/reducer.ts` | T0 | 4 | Pure reducer — ProjectionState functional update |

---

## Layer C — Gate & Risk (Gate 6)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/gate/hoeffding.ts` | T0 | 6 | Bernstein anytime-valid confidence bounds |
| `src/gate/risk.ts` | T0 | 6 | RiskBudgetManager — harmonic spending, LCB evaluation |

---

## Layer D — Pipeline (Gate 7)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/pipeline/` | T1 | 7 | End-to-end decision pipeline (E1→E2→E4→output) |

---

## Layer E — Environment Substrate (Gate 8)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/environment/memory/mutation_ledger.ts` | T0 | 8 | Append-only mutation ledger |
| `src/environment/workspace/introspection.ts` | T1 | 8 | FNV-1a workspace introspection |

---

## Layer F — Compliance & Registry (Gate 8)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/compliance/` | T1 | 8 | Policy compliance registry |
| `src/registry/` | T1 | 8 | Component registration |

---

## Layer G — Agent Ecology + IDE Nervous System (Gate 11)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/agents/types.ts` | T0 | 11 | 8 AgentType literals, CoordinationFrame, WorkflowExecution |
| `src/agents/coordination/AgentCoordinator.ts` | T0 | 11 | Multi-agent scheduling with replay safety |
| `src/agents/registry/agent-registry.ts` | T0 | 11 | T0/T1/T2 agent registration; T3+ rejected |
| `src/agents/scheduler/scheduler.ts` | T0 | 11 | Deterministic schedule builder, pressure metric |
| `src/agents/memory/agent-memory.ts` | T0 | 11 | Append-only agent memory with replay completeness |
| `src/agents/telemetry/agent-telemetry.ts` | T1 | 11 | 6-metric telemetry snapshot builder |
| `src/agents/workflows/types.ts` | T0 | 11 | 7 built-in workflows, WorkflowReplayFrame |
| `src/agents/workflows/workflow-engine.ts` | T0 | 11 | WorkflowEngine with replay integrity tracking |
| `src/ide/types.ts` | T1 | 11 | 10 IDE panel interfaces, IDERuntimeState |
| `src/ide/workspace/WorkspaceMemoryGraph.ts` | T1 | 11 | Agent workspace graph, lineage tracing |
| `src/ide/panels/panel-state.ts` | T1 | 11 | 10 pure panel factory functions |
| `src/ide/orchestration/orchestrator.ts` | T1 | 11 | IDEOrchestrator — panel state coordinator |

Test count after Gate 11: ~373 tests

---

## Layer H — SITR Constitutional Runtime Immunity (Gate 12)

**Epistemic Tier: T0 (constitutional enforcement)**

SITR is the active immune system of the AEGIS runtime. It detects anomalies,
issues ContainmentDirective[] as E5 events (phase 3 of the frame execution contract),
and escalates state monotonically through the 6-level SITRState lattice.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/sitr/types.ts` | T0 | 12 | SITRState lattice, ContainmentDirective, InterventionRecord |
| `src/sitr/lattice.ts` | T0 | 12 | stateOrdinal, canEscalateTo, escalate, isTerminalState |
| `src/sitr/telemetry.ts` | T1 | 12 | buildSITRTelemetry, computeEscalationRate |
| `src/sitr/intervention.ts` | T0 | 12 | InterventionLog — append-only, monotonic sequence |
| `src/sitr/replay.ts` | T0 | 12 | ReplayViolationLog — permanent, cumulative |
| `src/sitr/orchestration.ts` | T0 | 12 | detectOrchestrationAnomalies, anomalyToRequiredState |
| `src/sitr/runtime.ts` | T0 | 12 | SITRRuntime — observe(), issueDirective(), immutable update |

SITR rules: RULE-01..10 (see docs/SITR_CONSTITUTION.md)

---

## Layer I — AOIE Structural Classification Oracle (Gate 12)

**Epistemic Tier: T1 (structural classification, passive)**

AOIE is a pure function oracle. It observes post-enforcement snapshots only
(phase 5 of the frame execution contract) and classifies GlobalState.
AOIE has no stored state, no side effects, no runtime mutations.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/aoie/types.ts` | T1 | 12 | GlobalState, AOIEClassification, RuntimeSnapshot, SnapshotPhase |
| `src/aoie/canonicalize.ts` | T1 | 12 | JCS canonical serialization for AOIE types |
| `src/aoie/hash.ts` | T1 | 12 | FNV-1a snapshot hash, snapshotsAreIdentical, computeIdentityDrift |
| `src/aoie/arbitration.ts` | T1 | 12 | classifyArbitration — RESOLVED/CONTESTED/DEADLOCKED |
| `src/aoie/identity.ts` | T1 | 12 | classifyIdentityContinuity — CONTINUOUS/DRIFTED/BROKEN |
| `src/aoie/drift.ts` | T1 | 12 | classifyConstitutionalDrift — STABLE/DRIFTING/DIVERGED |
| `src/aoie/lattice.ts` | T1 | 12 | classifyGlobalState, compareGlobalStates, AOIE_SEVERITY_ORDER |
| `src/aoie/freeze.ts` | T1 | 12 | freezeClassification, freezeSnapshot |
| `src/aoie/runtime.ts` | T1 | 12 | classifyRuntime() — pure function with phase guard (SITRConstraintError) |

Phase guard invariant: `classifyRuntime()` throws `SITRConstraintError` if any
`RuntimeSnapshot.phase !== 'post_enforcement'`. AOIE must never observe uncommitted state.

Test count after Gate 12: ~409 tests

---

## Layer J — Constitutional Governance Surface (Gate 13)

**Epistemic Tier: T0 (constitutional verdict engine)**

The CGS closes the governance feedback loop. It consumes SITR state + AOIE
GlobalState + invariant check results, and produces a canonical ConstitutionalVerdict
emitted as Guardian E5 events (GUARDIAN_INVOKED + GUARDIAN_VERDICT_ISSUED).

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/constitutional/types.ts` | T0 | 13 | ConstitutionalVerdict, GovernanceDecision, SystemHealthSnapshot |
| `src/constitutional/verdict.ts` | T0 | 13 | computeVerdict(), verdictReason() — pure functions |
| `src/constitutional/guardian.ts` | T0 | 13 | buildGuardianInvokedPayload(), buildGuardianVerdictPayload() |
| `src/constitutional/assembly.ts` | T0 | 13 | ConstitutionalAssembly — append-only GovernanceDecision log |
| `src/constitutional/convergence.ts` | T1 | 13 | ConvergenceSurface — RalphLoop integration, convergence depth |
| `src/constitutional/runtime.ts` | T0 | 13 | ConstitutionalRuntime — composition entry point |

Verdict lattice: ESCALATE > REJECT > DEFER > PERMIT

| Verdict | Condition |
|---------|-----------|
| ESCALATE | T0 violation OR SITR=COMPROMISED OR AOIE=COMPROMISED |
| REJECT | SITR=CONSTITUTIONAL_RISK OR SITR=CONTAINED |
| DEFER | SITR=UNSTABLE/DEGRADED OR AOIE=ALERT |
| PERMIT | SITR=STABLE AND AOIE=SECURE AND no violations |

Test count after Gate 13: ~445 tests

---

## Layer K — Frame Execution Kernel + Enforcement Engine (Gate 14)

**Epistemic Tier: T0 (universal execution primitive)**

Gate 14 introduces the canonical `runFrame()` kernel — the T0 expression of the
Subatomic Holon Particle (SHP) execution model. Every holonic scale executes
identical R→A→L→P→H semantics. The commitment boundary (LOCK = phase 4) separates
SITR (pre-commit constraint evaluator) from AOIE (post-commit structural observer).

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/enforcement/types.ts` | T0 | 14 | EnforcementDecision, EnforcementResult, EnforcementOutcome |
| `src/enforcement/engine.ts` | T0 | 14 | applyDirectives() — pure function, deterministic phase 4 |
| `src/frame/types.ts` | T0 | 14 | FrameInput, FrameExecutionResult, FramePhaseTrace |
| `src/frame/snapshot.ts` | T0 | 14 | capturePostEnforcementSnapshot() — phase 4→5 bridge |
| `src/frame/directives.ts` | T0 | 14 | computeAutoDirectives() — deterministic FNV-1a IDs |
| `src/frame/kernel.ts` | T0 | 14 | runFrame() — canonical 7-phase composition kernel |
| `src/frame/shp.ts` | T0 | 14 | SHP_PHASES, toRalphTrace() — formal SHP identity |

SHP formal lock:
```
SHP_LOOP = 'R→A→L→P→H'
SHP_COMMITMENT_BOUNDARY = 'LOCK'
SITR ∈ { pre-commit phases: READ, ASSESS }
AOIE ∈ { post-commit phases: PROPAGATE, HARMONIZE }
SITR ∩ AOIE = ∅ (by LOCK boundary)
```

Test count after Gate 14: ~470 tests (28 files → 28+ files)

---

## Full Holonic Hierarchy

```
[Subatomic]  byte invariants, hash chaining, fixed-point arithmetic
[Atomic]     individual files — each a complete holon with declared invariants
[Molecular]  modules: core/, event/, gate/, calibration/, agents/, ide/, sitr/, aoie/, constitutional/, enforcement/, frame/, shp/, ledger/, consensus/, crdt/, network/
[Cellular]   subsystems: Agent Ecology, SITR Immunity, AOIE Oracle, Constitutional Assembly, Frame Kernel, Merkle Replay Ledger, HotStuff Ω Consensus (Ed25519), CRDT Lattice, Policy Amendment Engine, Byzantine Transport Harness
[Organism]   sovereign-omega-v2 governance runtime (Gates 1–26)
[FIELD]      AOIE + Claude + ChatGPT + Qwen + Drive corpus + operators
```

SHP(n) = recursive instantiation of R→A→L→P→H at holonic scale n.
A T0 violation at SUBATOMIC propagates upward and invalidates every scale above it.

---

## Seven-Phase Deterministic Frame Execution Contract (R→A→L→P→H)

| Phase | RALPH | System | Description |
|-------|-------|--------|-------------|
| 1 | **R** READ | Agents + IDE | Input intake; events appended to E5 |
| 2 | — | E5 | Immutable append commit; causal boundary closes |
| 3 | **A** ASSESS | SITR | Reads post-commit E5; emits ContainmentDirective[] back into E5 |
| 4 | **L** LOCK | Enforcement | Apply directives; freeze EnforcementResult |
| 5 | **P** PROPAGATE | AOIE | Reads post-enforcement snapshot; classifies GlobalState |
| 6 | **H** HARMONIZE | CGS | Reads SITR + AOIE + invariants → GovernanceDecision + Guardian E5 events |
| 7 | Frame finalization | Hash committed; replay checkpoint stored |

---

## Layer L — SHP Execution Identity Primitives (Gate 15)

**Epistemic Tier: T0 (subatomic — foundational type layer)**

Gate 15 crystallizes the SHP model into a standalone `src/shp/` module — the pure
type system and invariant registry that every holonic scale must satisfy. This layer
sits below all others: it defines the formal execution identity that `runFrame()`
(Layer K) instantiates at the ORGANISM scale.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/shp/types.ts` | T0 | 15 | Phase, SHP_PHASE_ORDER, phaseOrdinal, SHPExecutionIdentity |
| `src/shp/execution.ts` | T0 | 15 | SHPKernel interface, SHP_EXECUTION_INVARIANTS (8 rules), SHPInvariantId |
| `src/shp/guard.ts` | T0 | 15 | checkSHPInvariants(), validatePhaseTransition(), validatePhaseSequence() |
| `src/shp/factory.ts` | T0 | 15 | Phase-specific identity factories with FNV-1a deterministic commitHash |

Eight formal invariants: INV-SHP-01..08 (see `src/shp/execution.ts` and `docs/SHP_EXECUTION_MODEL.md`)

Field presence contract (enforced at factory construction + runtime guard):
- `classification` must not exist in READ/ASSESS phases (INV-SHP-06)
- `constraintResult` must not exist in PROPAGATE/HARMONIZE phases (INV-SHP-07)
- `commitHash` must be non-empty (INV-SHP-08)

Test count after Gate 15: **471 tests, 29 files**

---

## Layer M — Merkle Replay Ledger (Gate 17)

**Epistemic Tier: T0 (cryptographic replay integrity)**

Gate 17 introduces an append-only hash-chained ledger for full replay integrity.
Every frame that commits through the LOCK boundary produces a `LedgerEntry` whose
`previous_hash` is the SHA-256 of the preceding entry. `verifyChain()` proves the
chain is tamper-evident; `captureCheckpoint()` produces a frozen Merkle snapshot.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/ledger/types.ts` | T0 | 17 | LedgerEntry, LedgerSnapshot, LedgerConstraintError, GENESIS_HASH |
| `src/ledger/chain.ts` | T0 | 17 | LedgerChain — append-only immutable chain; throws on non-monotonic sequence |
| `src/ledger/checkpoint.ts` | T0 | 17 | captureCheckpoint() — frozen Merkle snapshot (JCS + SHA-256 per leaf) |
| `src/ledger/verify.ts` | T0 | 17 | verifyChain() async (full hash chain); verifySequences() sync (structural) |

Invariants:
- `entry[0].previous_hash === GENESIS_HASH` ('0'.repeat(64))
- `entry[i].previous_hash === sha256(entry[i-1])` for i > 0
- Sequence numbers are strictly monotonically increasing
- All snapshots are `deepFreeze`-d; Merkle root is byte-identical to Rust WASM output

Test count after Gate 17: **518 tests, 31 files**

---

## Layer N — TLA+ Extended Formal Model (Gate 18)

**Epistemic Tier: T0 (mechanically specified formal model)**

Gate 18 extends the TLA+ formal specification to cover the LOCK commitment boundary
and the SITR/AOIE phase separation invariants proven in Layers H, I, and L.

| Spec | Gate | Properties proven |
|------|------|-------------------|
| `formal/tlaplus/Omega.tla` | 18 | `LOCK_INVARIANT`: locked ⇒ UNCHANGED <<state>>; `AOIE_POST_COMMIT`: phase ∈ POST_COMMIT_PHASES ⇒ locked |
| `formal/tlaplus/SHP.tla` | 18 | `SITR_AOIE_SEPARATION`: PreLockPhases ∩ PostLockPhases = ∅; `COMMIT_HASH_INVARIANT`: commit_hash ≠ "" ⟺ locked; `SEQUENCE_MONOTONE`: sequence' ≥ sequence |

SHP.tla models the full 5-phase cycle (READ→ASSESS→LOCK→PROPAGATE→HARMONIZE) with
the commitment boundary as the sole irreversible transition (INV-SHP-02).
HarmonizeToRead resets `locked` and increments `sequence`, beginning a new frame.

---

## Layer O — HotStuff Ω Consensus Stub (Gate 19)

**Epistemic Tier: T2 (engineering hypothesis — deterministic BFT stub)**

Typed deterministic stub of the HotStuff BFT protocol (Yin et al. 2019).
Validators vote on replay equivalence (matching `frame_hash`), not semantic truth.
No network I/O — consensus is a pure function over vote sets.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/consensus/types.ts` | T2 | 19 | ValidatorId, Vote, QuorumCertificate, ConsensusBlock, ValidatorSet |
| `src/consensus/crypto.ts` | T2 | 19 | signVote/verifyVote — synchronous FNV-1a stub (Ed25519 seam) |
| `src/consensus/quorum.ts` | T2 | 19 | validateValidatorSet (n≥3f+1), collectValidVotes, isQuorum, formQC |
| `src/consensus/kernel.ts` | T2 | 19 | runConsensusRound() — pure (block, vs, votes) → ConsensusResult |

Safety: threshold = 2f+1; invalid/duplicate/unknown-validator votes rejected; QC `deepFreeze`-d.

Test count after Gate 19: **545 tests, 32 files**

---

## Layer P — CRDT Convergence Lattice (Gate 20)

**Epistemic Tier: T2 (engineering hypothesis — monotonic merge)**

Monotonic semilattice join operations for distributed state merge.
All joins satisfy: commutativity, associativity, idempotency, monotonicity.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/crdt/types.ts` | T2 | 20 | CRDTConflictError |
| `src/crdt/sitr.ts` | T2 | 20 | joinSITRState() — max in escalation order; foldSITRStates(); sitrLeq() |
| `src/crdt/verdict.ts` | T2 | 20 | joinVerdict() — most-restrictive wins; foldVerdicts(); verdictLeq() |
| `src/crdt/ledger.ts` | T2 | 20 | joinLedgerEntries() — G-Set CRDT; CRDTConflictError on fork |

Lattice bottoms: SITRState → 'STABLE'; ConstitutionalVerdict → 'PERMIT'; LedgerEntries → [].

Test count after Gate 20: **570 tests, 33 files**

---

## Layer Q — Guardian Policy Runtime (Gate 21)

**Epistemic Tier: T0 (constitutional enforcement extension)**

Bounded policy amendment lifecycle with Guardian verdict gate.
All amendments flow through E5 as constitutional events. The runtime NEVER modifies
constitutional primitives directly — all changes are E5 events consumed by Phase 4.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/constitutional/amendment.ts` | T0 | 21 | PolicyAmendment, AmendmentStatus, PolicyAmendmentError |
| `src/constitutional/policy.ts` | T0 | 21 | PolicyAmendmentEngine — propose, recordVerdict, apply |

Amendment invariants:
- `apply()` requires `status === 'APPROVED'` (Guardian APPROVED verdict)
- `apply()` requires `invariants_passed === true` (no regression)
- amendment_id is deterministic: FNV-1a(target + delta + sequence)
- All amendments are `deepFreeze`-d; engine uses immutable functional update

Test count after Gate 21: **593 tests, 34 files**

---

## Layer R — Ed25519 Cryptographic Hardening (Gate 22)

**Epistemic Tier: T2 (replaces FNV-1a stub with production Ed25519)**

Closes the first of five production deployment surfaces. All validator vote signatures are now RFC 8032 / FIPS 186-5 Ed25519. The `ValidatorPublicKey` is the cryptographic identity; `ValidatorId` is the human reference. `generateKeypair(seed)` is the production seam — replace seed with CSPRNG output before distributed deployment.

| Change | Gate | Description |
|--------|------|-------------|
| `src/consensus/types.ts` | 22 | Added `ValidatorPublicKey`, `ValidatorKeyPair`, `ValidatorEntry`; updated `ValidatorSet` |
| `src/consensus/crypto.ts` | 22 | `signVote(privKey, blockHash)` + `verifyVote(pubKey, blockHash, sig)` via @noble/ed25519 v3 |
| `src/consensus/quorum.ts` | 22 | `collectValidVotes()` made async; public key lookup from `ValidatorEntry` |

Test count after Gate 22: **595 tests, 34 files**

---

## Layer S — Ledger Persistence Seam (Gate 23)

**Epistemic Tier: T0 (deterministic serialization contract)**

`src/ledger/persistence.ts` provides the crash-safe recovery contract. It does not connect to any database — it defines the exact serialization shape that any storage backend must honour. `serializeSnapshot` is RFC 8785 deterministic; `deserializeSnapshot` validates every field including BigInt sequences, 64-char hashes, schema_version, and `is_replay_reconstructable`.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/ledger/persistence.ts` | T0 | 23 | `serializeSnapshot`, `deserializeSnapshot`, `serializeChain`, `deserializeChain` |

Test count after Gate 23: **616 tests, 35 files**

---

## Layer T — Byzantine Transport Interface (Gate 24)

**Epistemic Tier: T2 (pure simulation harness — no actual network)**

`src/network/` is the typed deterministic transport stub. All operations are pure functions over sorted message arrays. The anti-equivocation invariant (same sender+sequence, different payload → NetworkError) is mechanically enforced. Real gossip transport (libp2p/QUIC) is deployment infrastructure; this module defines the contract.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/network/types.ts` | T2 | 24 | PeerId, MessageId, ReplayMessage, NetworkConfig, SimulationResult |
| `src/network/queue.ts` | T2 | 24 | DeterministicMessageQueue — sorted by message_id, dedup, anti-equivocation |
| `src/network/simulation.ts` | T2 | 24 | ByzantineSimulation — pure function, equivocation detection |
| `src/network/kernel.ts` | T2 | 24 | broadcastVote(), computeMessageId() — FNV-1a deterministic IDs |

Test count after Gate 24: **643 tests, 36 files**

---

## Layer U — Formal Proof Completion (Gate 25)

**Epistemic Tier: T0 (TLA+ mechanically specified models)**

Closes the formal verification surface with two new TLA+ modules proving the CRDT lattice laws and LOCK irreversibility theorem.

| Spec | Gate | Properties proven |
|------|------|-------------------|
| `formal/tlaplus/CRDTLattice.tla` | 25 | `IDEMPOTENT`: Join(s,s)=s; `COMMUTATIVE`: Join(a,b)=Join(b,a); `MONOTONE`: ord(Join(a,b))≥ord(a) |
| `formal/tlaplus/LockIrreversibility.tla` | 25 | `LOCK_ONCE_SET_STAYS_SET`: locked=TRUE cannot become FALSE within a frame; `SEQUENCE_INCREMENTS_ON_UNLOCK`: sequence strictly increases on frame reset; `PRE_POST_DISJOINT`: no phase is simultaneously pre- and post-lock |

---

## Layer V — README + System Documentation (Gate 26)

**Gate 26**: `sovereign-omega-v2/README.md` created — full system documentation including execution stack, build protocol, invariant table, module map, tier system, production readiness index, and what is explicitly NOT implemented.

---

## Layer W — WASM Replay Equivalence Proof (Gate 27)

**Epistemic Tier: T0 (mechanically proven cross-platform determinism)**

Gate 27 completes the implementation-invariant threshold: `H_TS(f_n) = H_WASM(f_n) ∀ governance frames`. Before this gate, the runtime was deterministic *within* TypeScript. After this gate, the constitutional machine is platform-independent — a WASM node and a TypeScript node processing identical governance state produce byte-identical frame hashes, enabling cross-platform replay equivalence voting.

**BigInt Contract (empirically verified):**
`canonicalizeJCS({sequence: 1n})` → `{"sequence":"1"}` — BigInt is serialized as a quoted decimal string. `JSON.stringify({sequence: 1n}, bigintReplacer)` produces `'{"sequence":"1"}'`. Both paths produce identical wire bytes; WASM equivalence holds for `LedgerEntry.sequence` (bigint) without pre-conversion in TypeScript.

**Five Proof Groups:**

| Proof | Subject | Assertion |
|-------|---------|-----------|
| A | SHA-256 parity on canonical governance bytes | `sha256Hex(canonicalBytes) === wasm_sha256(canonicalBytes)` for 5 governance objects + edge cases |
| B | Canonicalization parity on governance JSON | `canonicalizeJCS(obj)` bytes ≡ `wasm_canonicalize(JSON.stringify(obj, bigintReplacer))` bytes for key-ordering, escaping, nesting |
| C | End-to-end `hashValue()` equivalence | `hashValue(obj) === hex(wasm_sha256(wasm_canonicalize(json_str(obj))))` for 4 typed governance objects + 10 FNV-1a fixtures |
| D | Ledger chain link WASM-verifiable | `wasm_sha256(wasm_canonicalize(entry_json)) === next_entry.previous_hash` for all 5 chain links, 3 passes |
| E | Merkle checkpoint equivalence | `computeMerkleRootFromValues(entries) === hex(wasm_merkle_root(wasm_canonical_leaves))` for 1/3/4/5 entries and empty |

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `test/determinism/replay-equivalence.test.ts` | T0 | 27 | 26-test WASM replay equivalence harness (5 proof groups) |

Divergence surfaces closed by Gate 27:
- **BigInt/i64 semantics**: proven via Proof C (LedgerEntry with real bigint sequence)
- **UTF-8 canonicalization**: proven via Proof B (string-escape stress, Unicode keys)
- **Object key ordering**: proven via Proof B (reverse-alphabetical 10-key, mixed-case ASCII ordering)
- **Endian assumptions**: proven via Proof A (SHA-256 byte output on canonical governance bytes)

Test count after Gate 27: **669 tests, 37 files**

---

## Layer X — SHP Transition Certifier / Replay DFA (Gate 28)

**Epistemic Tier: T0 (mechanically enforced phase ordering)**

Closes the gap between the TLA+ formal specification and the runtime. The SHP 5-phase cycle is now a DFA — invalid phase transitions throw `SHPExecutionError` at runtime. Each phase boundary produces a `FrameTransitionRecord` with a chained `transition_hash`, forming a tamper-evident cryptographic proof log of execution order. `certifyExecution()` re-derives all hashes independently and returns an `ExecutionCertificate`.

Invariants enforced: INV-SHP-01 (ASSESS before LOCK), INV-SHP-02 (LOCK is single commit point), INV-SHP-05 (no phase reordering or skipping).

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/frame/dfa.ts` | T0 | 28 | `SHPTransitionMachine`, `transition()`, `certifyExecution()`, `FrameTransitionRecord`, `ExecutionCertificate` |

Test count after Gate 28: **697 tests, 38 files**

---

## Layer Y — Topology Hash Engine (Gate 29)

**Epistemic Tier: T0 (constitutional identity law)**

Implements `ConstitutionalIdentity(T) = TopologyHash(T)`. A `GovernanceTopology` is the complete fingerprint of one governance epoch: SITR state + AOIE global state + constitutional verdict + ledger Merkle root + consensus QC hash + DFA certificate hash. `topologiesConverge(a, b)` checks byte-identical `topology_hash` values — the constitutional convergence test. `verifyTopology()` re-derives the hash from fields to detect tampering.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/frame/topology.ts` | T0 | 29 | `GovernanceTopology`, `buildTopology()`, `computeTopologyHash()`, `topologiesConverge()`, `verifyTopology()` |

Test count after Gate 29: **721 tests, 39 files**

---

## Layer Z — Replay Lineage Certifier (Gate 30)

**Epistemic Tier: T0 (constitutional causal chain)**

`TopologyLineage` is an append-only chain of `GovernanceTopology` snapshots where `entry[n].previous_topology_hash = entry[n-1].topology_hash`, anchored to `GENESIS_TOPOLOGY_HASH`. Provides the full causal history of constitutional state transitions. `certifyLineage()` re-derives every `lineage_hash` independently and verifies the hash chain — enabling a node joining mid-session to verify all prior epochs without trusting the peer's state.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/frame/lineage.ts` | T0 | 30 | `TopologyLineage`, `buildLineageEntry()`, `certifyLineage()`, `computeLineageHash()`, `LineageCertificate` |

Test count after Gate 30: **742 tests, 40 files**
