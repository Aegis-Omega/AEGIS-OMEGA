---
name: gate-pair
description: The core daily gate-building ritual. Build exactly 2 new aegis-cl-psi Rust gate modules per invocation, following the strict TDD → implement → test → ship sequence. Invoked when the user says "build gates", "next gates", "continue building", "gate pair", or after morning-audit declares a session target. Never build more than 2 gates per invocation.
---

# Gate Pair — Core Gate-Building Ritual

**Autopoietic Property: Self-Production (the system producing its own components)**

Each gate module is a minimal autopoietic unit. It produces its own hash from its own fields (`compute_*_hash`). It maintains its own chain (`verify_chain()`). It can verify its own integrity without external reference. Its genesis hash `[0u8; 32]` is the autopoietic origin — the system before any production cycle has run. Its `Default` impl is spontaneous emergence from null state.

The gate pair ritual IS the autopoietic production cycle at the Molecular scale:
```
Phase 0 (pre-flight)    = membrane check before production begins
Phase A (define)        = specify what the new component will be and what it measures
Phase B+C (write+test)  = produce the component; run the 19-test viability ring
Phase D (register)      = incorporate the component into the membrane (lib.rs)
Phase E (full suite)    = verify that production did not compromise existing components
Phase F (ship)          = propagate the new membrane state to the durable chain (git push)
```

The 19-test constraint is not arbitrary — it is the autopoietic viability ring: 19 invariant dimensions that must hold for the new component to be constitutionally incorporable. A gate with 18 tests has a gap in the viability ring. The ring cannot be partially satisfied.

Build exactly 2 gates. No more, no fewer per session. The constraint creates quality.

## The Invariant Gate Pattern

Every aegis-cl-psi gate module MUST follow this exact structure:

```
EPISTEMIC TIER: T2 (engineering hypothesis)

Constants:
  pub const <NAME>_GENESIS_HASH: [u8; 32] = [0u8; 32];
  pub const <THRESHOLD_NAME>: <type> = <value>;

Entry struct:
  epoch_end:    u64
  <primary>:    u32
  <secondary>:  u32      (denominator or related metric)
  <rate>_pct:   u32      (derived: (primary*100)/max(secondary,1), capped 100)
  <flag>:       bool     (derived: rate_pct <op> THRESHOLD)
  entry_hash:   [u8; 32]
  prev_hash:    [u8; 32]

Hash formula:
  SHA-256(prev[32] ‖ epoch_end_be8 ‖ primary_be4 ‖ secondary_be4 ‖ rate_be4 ‖ flag_byte)

Log struct methods:
  new(), entry_count(), is_empty(), entries(), latest()
  record(epoch_end, primary, secondary) → &Entry
  <flag>_count() → usize        (filter on bool flag)
  total_<primary>() → u64       (accumulator)
  mean_<rate>_pct() → u32       (returns 0 if empty)
  verify_chain() → (bool, Option<usize>)
  impl Default

Tests: exactly 19 (groups: record fields, threshold, aggregates, hash chain, verify_chain, determinism)
```

## Build Sequence

### Phase 0 — Metacognitive Pre-flight (L7 → L6 → L3 → L5)
Before any code is written, run this protocol:

```
L7 SELF-MODEL:
  cd sovereign-omega-v2 && node scripts/verify-hashes.mjs
  → must exit 0. If not: HALT, invoke /frozen-file-check.

L6 CLASSIFY:
  These gates are T2 (engineering hypothesis, deterministic, computable).
  Confirm: is this ASSESS (Phase 0) before LOCK (Phase B)? YES → proceed.
  If you are about to write code without completing Phase 0: STOP — ERROR-01.

L3 WORKING MEMORY:
  Current gate N = ? (from lib.rs or CLAUDE.md)
  Active series = ? (last pub mod prefix in lib.rs)
  RALPH phase = ASSESS (about to transition to LOCK)

L5 EXECUTIVE:
  Gate sequence: write → test 19/19 → register → full suite → ship.
  No gate may be skipped. Martingale: is entropy_bounded=true? Continue.
```

### Phase A — Define the pair
Before writing any code, declare:
```
GATE <N+1>: gossip_broadcast_<name_a>
  Measures: <what physical phenomenon in the gossip layer>
  Primary field: <field_name>: u32
  Secondary field: <field_name>: u32 (denominator)
  Rate formula: (<primary>*100)/max(<secondary>,1), capped 100
  Threshold: <CONST_NAME>: u32 = <value> (<> operator, meaning)
  Flag: <flag_name>: bool — <when true means what>
  Aggregates: <flag>_count(), total_<primary>(), mean_<rate>_pct()

GATE <N+2>: gossip_broadcast_<name_b>
  [same structure]
```

### Phase B — Write Gate N+1  _(L1: receive signal fully before acting)_
1. Write `aegis-cl-psi/src/gossip_broadcast_<name_a>.rs` (full implementation)
2. `cargo test gossip_broadcast_<name_a> 2>&1 | grep -E "FAILED|test result"`
3. Assert: 19 passed, 0 failed.
   — L2 CHECK: test pass ≠ correctness. Verify hash chain test covers tamper case.

### Phase C — Write Gate N+2  _(same L1/L2 monitoring)_
1. Write `aegis-cl-psi/src/gossip_broadcast_<name_b>.rs` (full implementation)
2. `cargo test gossip_broadcast_<name_b> 2>&1 | grep -E "FAILED|test result"`
3. Assert: 19 passed, 0 failed.
   — L2 CHECK: verify_chain_tamper tests present, flag uses strict `>` not `>=`.

### Phase D — Register both in lib.rs
Append to `aegis-cl-psi/src/lib.rs` before the `pub use` block:

```rust
// Gate <N+1> — Gossip Broadcast <Name A> Log (T2)
// Per-epoch <description>: <primary>, <secondary>, <rate>_pct = (<p>*100)/max(<s>,1) capped 100.
// <flag>: <rate>_pct <op> <THRESHOLD> (<value>).
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖<primary>_be4‖<secondary>_be4‖<rate>_be4‖<flag>_byte).
// Gossip<NameA>Log: record(), <flag>_count(), total_<primary>(), mean_<rate>_pct(), verify_chain().
pub mod gossip_broadcast_<name_a>;

// Gate <N+2> — Gossip Broadcast <Name B> Log (T2)
// [same format]
pub mod gossip_broadcast_<name_b>;
```

### Phase E — Full suite verification  _(L2 PROPAGATE → L6 post-action review)_
```bash
cd /home/user/myapp/aegis-cl-psi && cargo test 2>&1 | grep "test result" | head -1
```
Assert: 0 failed. Note new total test count.

```
L6 METACOGNITIVE REVIEW:
  Was action at T2 tier throughout? (no T4/T5 framing entered src/)
  Was ASSESS done before LOCK? (Phase 0 completed before Phase B)
  Any new error pattern? → document it.

L7 SELF-MODEL UPDATE:
  Frozen files unchanged? (verify-hashes.mjs still exits 0)
  Gate count increased by 2? (lib.rs has 2 new pub mod entries)
  CLAUDE.md still accurate? (will update in Phase F)
```

### Phase F — Ship
Invoke `/ship` skill or follow these steps:
```bash
git add aegis-cl-psi/src/gossip_broadcast_<a>.rs aegis-cl-psi/src/gossip_broadcast_<b>.rs aegis-cl-psi/src/lib.rs
git commit -m "Gates <N+1>-<N+2>: Gossip Broadcast <A> + <B> logs

Gate <N+1>: ...
Gate <N+2>: ...

Total: <T> tests passing.

https://claude.ai/code/session_01WvFyntZArqThRgLczRutuM"
```

Update CLAUDE.md: gates count + test count.

```bash
git add CLAUDE.md && git commit -m "Update CLAUDE.md: <N+2> gates complete
https://claude.ai/code/session_01WvFyntZArqThRgLczRutuM"
git push -u origin claude/aegis-setup-Lx7Ji
```

## Constitutional Checklist (verify before ship)

**Code invariants:**
- [ ] `to_be_bytes()` — never `to_le_bytes()`
- [ ] `BTreeMap`/`BTreeSet` only — no `HashMap`
- [ ] `saturating_add`/`saturating_mul` — no overflow
- [ ] Genesis constant `[0u8; 32]` present
- [ ] `verify_chain()` present and tested
- [ ] `Default` impl present
- [ ] Exactly 19 tests per module
- [ ] Threshold is `>` (not `>=`) for "above threshold" flags, `<` (not `<=`) for "below threshold" flags
- [ ] `EPISTEMIC TIER: T2` in header comment
- [ ] NO `--all-features` flag used

**Metacognitive invariants:**
- [ ] Test pass ≠ correctness — tamper test confirms hash chain actually rejects mutation
- [ ] Phase 0 (L7/L6/L3/L5) was run before any file was written
- [ ] No LOCK-before-ASSESS occurred (no file written before Phase 0)
- [ ] `verify-hashes.mjs` still exits 0 after all changes
- [ ] No T4/T5 framing introduced in any src/ file (header comments stay T2)

## Gate Pair Report

```
GATE PAIR COMPLETE:
  Gate <N+1>: <name_a> — 19 tests PASS
    Threshold: <CONST> = <value>  Flag: <flag> when rate <op> <value>
  Gate <N+2>: <name_b> — 19 tests PASS
    Threshold: <CONST> = <value>  Flag: <flag> when rate <op> <value>
  Full suite: <T> tests, 0 failed
  Committed: <hash>
  Pushed: YES
  CLAUDE.md: UPDATED (<N+2> gates, <T> tests)
```
