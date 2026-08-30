---
name: drift-check
description: Constitutional drift detection. Scans the aegis-cl-psi codebase for invariant violations that creep in over hundreds of gates — wrong endianness, HashMap usage, missing verify_chain, overflow-unsafe arithmetic, incorrect threshold operators. Run weekly or when something feels off. Invoked when the user says "drift check", "constitutional scan", "invariant audit", "are we drifting", "membrane erosion", "slow degradation".
---

# Drift Check — Constitutional Invariant Scanner (Membrane Slow-Scan)

**Autopoietic Property: Membrane Slow-Scan — Detection of Gradual Boundary Erosion**

Unlike the `frozen-file-check` (which responds to acute boundary breach events), this skill detects **chronic membrane erosion** — the slow accumulation of invariant violations across hundreds of gates that each individually look harmless. Over 500+ gates, `to_le_bytes()` in one module, an unchecked `u32 +` in another, and a `HashMap` in a third compose into a constitutional drift that invalidates cross-platform replay.

This is the automaton performing periodic membrane self-inspection:
- **Self-production check**: Is every new gate component conforming to the structural pattern (19 tests, verify_chain, GENESIS_HASH, BE byte order)?
- **Boundary integrity scan**: Are any non-membrane materials (HashMap, LE bytes, wall-clock arithmetic) infiltrating the structural closure?
- **Viability signal**: Drift score NONE = viable. CRITICAL = production halted until membrane repaired.

**CRITICAL drift violations** immediately suspend gate work — these are membrane breaches, not suggestions.

Run systematically. Every finding is a real violation, not a suggestion. Fix before proceeding with gate work.

## Scan 1 — Endianness Drift (CRITICAL)
All hash inputs MUST use `to_be_bytes()`. Little-endian in any hash input breaks cross-platform replay.

```bash
grep -rn "to_le_bytes\|little_endian\|from_le_bytes" /home/user/AEGIS--/aegis-cl-psi/src/ \
  | grep -v "//\|test\|doc"
```

Assert: empty output.
If any found: FIX IMMEDIATELY — these break determinism for any peer running the same hash.

## Scan 2 — HashMap Usage (DETERMINISM VIOLATION)
`HashMap` has non-deterministic iteration order. Only `BTreeMap`/`BTreeSet` permitted.

```bash
grep -rn "HashMap\|use std::collections::Hash\|HashSet" /home/user/AEGIS--/aegis-cl-psi/src/ \
  | grep -v "//\|test"
```

Assert: empty output.

## Scan 3 — Missing verify_chain (INTEGRITY GAP)
Every `*Log` struct must have a `verify_chain()` method.

```bash
# Find all Log struct definitions
grep -l "pub struct Gossip.*Log\|pub struct .*Log {" /home/user/AEGIS--/aegis-cl-psi/src/*.rs \
  | xargs -I{} sh -c 'grep -L "verify_chain" "{}" && echo "MISSING: {}"'
```

Assert: no output (all log structs have verify_chain).

## Scan 4 — Overflow-Unsafe Arithmetic
All integer arithmetic must use `saturating_*` or `checked_*`. Bare `+`/`*` on u32/u64 can overflow silently.

```bash
# Look for arithmetic that isn't clearly saturating or in a min/max/capped context
grep -rn "\bu32\b.*+\|\bu64\b.*+" /home/user/AEGIS--/aegis-cl-psi/src/ \
  | grep -v "saturating\|checked\|min(100\|.min\|test\|//\|use \|impl\|fn \|struct\|pub const"
```

Manual review required for any matches. Each must be verified safe (constant bounds or saturating arithmetic).

## Scan 5 — Missing Default Impl
Every `*Log` struct must implement `Default`.

```bash
grep -n "^pub struct.*Log" /home/user/AEGIS--/aegis-cl-psi/src/*.rs | \
  awk -F: '{print $1}' | sort -u | \
  xargs -I{} sh -c 'grep -L "impl Default" "{}" && echo "MISSING Default: {}"'
```

## Scan 6 — Genesis Hash Naming Convention
Every gate module must declare its genesis constant as `pub const <MODULE_UPPER>_GENESIS_HASH: [u8; 32] = [0u8; 32];`

```bash
grep -rL "GENESIS_HASH" /home/user/AEGIS--/aegis-cl-psi/src/gossip_*.rs \
  | grep -v "test\|broadcaster\b"
```

Assert: empty (all gossip modules have GENESIS_HASH).

## Scan 7 — all-features Guard (CI SAFETY)
The `hip` and `rocblas` features must never be activated in test commands.

```bash
grep -rn "all-features\|--features hip\|--features rocblas" /home/user/AEGIS--/.claude/ \
  /home/user/AEGIS--/CLAUDE.md 2>/dev/null | grep -v "NEVER\|never\|prohibited\|not\|without"
```

Assert: empty (or only "never use --all-features" warning references).

## Scan 8 — lib.rs Registration Coverage
Every `.rs` file in `src/` should have a corresponding `pub mod` in `lib.rs`.

```bash
# Files not registered
comm -23 \
  <(ls /home/user/AEGIS--/aegis-cl-psi/src/*.rs | xargs -n1 basename | sed 's/\.rs$//' | grep -v "^lib$" | sort) \
  <(grep "^pub mod" /home/user/AEGIS--/aegis-cl-psi/src/lib.rs | awk '{print $3}' | tr -d ';' | sort)
```

Assert: empty. Any file not in lib.rs is dead code — either delete it or register it.

## Scan 9 — Epistemic Tier Tags
Every new gate file must have `EPISTEMIC TIER: T2` in its header comment.

```bash
grep -rL "EPISTEMIC TIER" /home/user/AEGIS--/aegis-cl-psi/src/gossip_*.rs 2>/dev/null
```

Assert: empty.

## Scan 10 — Test Count Verification
Confirm the test count in CLAUDE.md is accurate.

```bash
cd /home/user/AEGIS--/aegis-cl-psi && cargo test 2>&1 | grep "test result" | head -1
grep "tests)" /home/user/AEGIS--/CLAUDE.md
```

If mismatch: update CLAUDE.md.

## Drift Check Report

```
DRIFT CHECK REPORT — <date>
════════════════════════════════════════
Endianness (to_le_bytes):      CLEAN / VIOLATIONS: <list>
HashMap usage:                 CLEAN / VIOLATIONS: <list>
Missing verify_chain:          CLEAN / GAPS: <list>
Overflow arithmetic:           CLEAN / REVIEW: <list>
Missing Default impl:          CLEAN / GAPS: <list>
Genesis hash naming:           CLEAN / GAPS: <list>
all-features guard:            CLEAN / VIOLATIONS: <list>
lib.rs registration:           CLEAN / UNREGISTERED: <list>
Epistemic tier tags:           CLEAN / MISSING: <list>
Test count accuracy:           SYNCED / MISMATCH: <diff>

DRIFT VERDICT: NONE / MINOR (<N> fixable) / CRITICAL (halt gate work)
════════════════════════════════════════
```

`CRITICAL` violations: endianness, HashMap, missing verify_chain. Fix before any new gate work.
`MINOR` violations: fix within current session before evening-seal.
