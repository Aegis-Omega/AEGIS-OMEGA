---
name: tdd
description: Test-driven development workflow for AEGIS gate modules. Invoked when writing a new Rust gate (aegis-cl-psi) or TypeScript module. Enforces: write the test contract first, then the implementation, never the reverse. Guarantees constitutional invariants are encoded in tests before any code exists.
---

# TDD Skill — AEGIS Gate Development Protocol

**Metacognitive Layer: L1 (Sensation) + L2 (Perception) + L6 (Metacognition)**

TDD is the L1→L2 signal verification protocol applied to implementation. You do not write code into the dark — you write a test that tells you when the signal (implementation) is correct. The test IS the L2 perception filter: it tells you when reality matches the spec, and it cannot be fooled by your own reasoning about what should work.

L1 invariant: **Read the complete type definition before writing any test against it.**
L2 invariant: **Test pass ≠ Correctness. The tamper test (verify_chain_detects_tamper) is the minimum proof that the hash chain actually rejects mutation — not just that it runs.**
L6 invariant: **ASSESS (write tests first, understand the contract) before LOCK (write implementation). Reversing this is ERROR-01.**

**Autopoietic Property: Viability Ring (19-test production validation)**

The 19-test structure is the autopoietic viability ring — the minimum set of dimensions that must hold for a new component to be constitutionally incorporable. Writing the tests first is writing the viability specification before producing the component. The implementation is not the goal; passing the viability ring is the goal. An implementation that passes all 19 tests has been verified to be a self-consistent unit that can be incorporated into the membrane without breaking the chain.

The `verify_chain_detects_tamper` test is the autopoietic integrity test: it verifies that the component can detect attacks on its own structure. A component that cannot detect tampering is a membrane breach waiting to happen.

Write the test structure before the implementation. The implementation exists only to make the tests pass.

## Gate Module TDD Protocol (Rust — aegis-cl-psi)

### Phase 1: CONTRACT (write first, before implementation)

Define the test structure for the new gate. Every gate module must include exactly these test groups:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────
    // WRITE: record_fields_stored, zero_input_zero_rate, denominator_zero_uses_max_one,
    //        rate_capped_at_100

    // ── threshold / boolean flag ──────────────────────────────────────────────
    // WRITE: below_threshold_not_flagged, at_threshold_boundary (exactly at = NOT flagged),
    //        above_threshold_flagged

    // ── aggregate stats ───────────────────────────────────────────────────────
    // WRITE: flag_count_correct, total_accumulator_correct, mean_rate_correct,
    //        mean_rate_empty_zero, total_empty_zero

    // ── hash chain ────────────────────────────────────────────────────────────
    // WRITE: entry_hash_nonzero, first_entry_prev_hash_is_genesis, chain_prev_links

    // ── verify_chain ──────────────────────────────────────────────────────────
    // WRITE: verify_chain_empty_ok, verify_chain_multiple_ok, verify_chain_detects_tamper

    // ── determinism ───────────────────────────────────────────────────────────
    // WRITE: entry_hash_deterministic (two independent logs, same inputs → same hash)
}
```

**Constitutional invariants that MUST be tested:**
1. `rate_capped_at_100` — input > denominator never exceeds 100
2. `denominator_zero_uses_max_one` — division by zero handled
3. `at_threshold_boundary` — threshold is strict `>` not `>=` (or `<` not `<=`)
4. `verify_chain_detects_tamper` — XOR one byte, assert (false, Some(0))
5. `entry_hash_deterministic` — same inputs ×2 independent logs → identical hash

### Phase 2: STUB IMPLEMENTATION

Create the file with types only, no logic:
```rust
pub const GOSSIP_<NAME>_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const <THRESHOLD_NAME>: u32 = <value>;

#[derive(Debug, Clone, PartialEq)]
pub struct Gossip<Name>Entry {
    pub epoch_end:    u64,
    pub <field_a>:   u32,
    pub <field_b>:   u32,
    pub <rate_field>: u32,
    pub <flag_field>: bool,
    pub entry_hash:   [u8; 32],
    pub prev_hash:    [u8; 32],
}

pub struct Gossip<Name>Log { entries: Vec<Gossip<Name>Entry> }
```

Run tests — they should FAIL (compile error or logic error). This confirms the tests are real.

### Phase 3: IMPLEMENTATION

Implement in this order:
1. `compute_<name>_hash()` — the SHA-256 function
2. `impl Gossip<Name>Log` — `new()`, `record()`, accessors, aggregates, `verify_chain()`
3. `impl Default`

Run tests after each function. Assert they go from FAIL → PASS incrementally.

### Phase 4: VERIFY INVARIANTS

After all tests pass:
```bash
cargo test <module_name> 2>&1 | grep -E "FAILED|test result"
```
Assert: 0 FAILED, exactly 19 tests (standard gate module has 19 tests).

Check the formula in the header comment matches the implementation:
- `compute_<name>_hash` field order = header comment field order
- Threshold comparison direction (`>`, `<`, `>=`, `<=`) is consistent

### Phase 5: REGISTER AND SHIP

Register in `lib.rs` with the canonical comment block:
```rust
// Gate <N> — Gossip <Name> Log (T2)
// Per-epoch <description>: <field_a>, <field_b>, <rate_field> = (<a>*100)/max(<b>,1) capped 100.
// <flag_field>: <rate> <op> <THRESHOLD> (<value>).
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖<fields>_be4‖<flag>_byte).
// Gossip<Name>Log: record(), <flag>_count(), total_<accumulator>(),
//   mean_<rate>_pct(), verify_chain().
pub mod gossip_<name>;
```

Then invoke `/ship`.

## Reporting Format

```
TDD GATE <N>:
  Phase 1 (contract): <N> test stubs written
  Phase 2 (stub):     Tests FAIL as expected
  Phase 3 (impl):     Implementation complete
  Phase 4 (verify):   <19> tests PASS, 0 FAIL
  Threshold:          <NAME> = <value> (<direction>)
  Formula:            <rate_field> = (<a>*100)/max(<b>,1) capped 100
  Invariants:         ALL PRESENT
  Ready for /ship:    YES
```
