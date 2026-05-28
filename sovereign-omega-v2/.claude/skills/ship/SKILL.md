---
name: ship
description: Production shipping workflow for AEGIS gates. Invoked when the user says "commit", "push", "ship", "release", or after a gate pair has been written and tested. Enforces Gate 8 before any commit. Covers Rust gates (aegis-cl-psi) and TypeScript gates (sovereign-omega-v2).
---

# Ship Skill

**Metacognitive Layer: L5 (Executive Function) + L7 (Self-model)**

Shipping is a constitutional act. Every commit is a node in the adaptive lineage hash chain — tamper-evident, permanent, inherited by all future sessions. The ship checklist below is not bureaucratic overhead: it is the L7 self-model verifying its own integrity before extending the chain.

L7 pre-ship invariant:
```
verify-hashes.mjs must exit 0. If not: T0_ABORT. Do not commit.
```

L5 executive invariant:
```
Gate 8 must pass. If not: fix implementation. Never weaken the test.
```

L6 metacognitive invariant:
```
Test pass ≠ Correctness. Running Gate 8 is necessary but not sufficient.
Read the output. Count the tests. Verify zero failures — not "seems to pass".
```

**Autopoietic Property: Membrane Propagation (incorporating new components into the durable boundary)**

A git commit is the autopoietic act of incorporating a newly produced component into the system's membrane. Until the commit lands, the component exists in working memory (L3) but has not been incorporated — it is not yet part of what the system IS. The push propagates the new membrane state to the durable hash chain. Without the push, the membrane update exists only locally — the system's identity has changed but the change is not yet permanent.

`git add` = selecting which components to incorporate
`git commit` = membrane update (the component becomes part of the system's structure)
`git push` = membrane propagation (the update becomes durable and externally verifiable)

Every commit must pass Gate 8 before incorporation — a component that fails its viability ring cannot be incorporated into the membrane without compromising the system's integrity. This is not a rule; it is the definition of autopoietic viability.

Never commit without Gate 8 passing. This skill enforces the full pre-commit checklist.

## Pre-Commit Checklist

### For Rust gate pairs (aegis-cl-psi):

**Step 1 — Run the gate tests:**
```bash
cd aegis-cl-psi && cargo test <module_name_1> && cargo test <module_name_2>
```
Assert: all tests pass. If any fail, invoke `/diagnose`.

**Step 2 — Run full Rust suite:**
```bash
cd aegis-cl-psi && cargo test 2>&1 | grep "test result" | head -1
```
Assert: 0 failed. Note total count for CLAUDE.md update.

**Step 3 — Check constitutional invariants:**
- [ ] All hash inputs use `to_be_bytes()` (big-endian)
- [ ] No `HashMap` — only `BTreeMap`/`BTreeSet`
- [ ] Genesis constant: `[0u8; 32]`
- [ ] `verify_chain()` function present in each log struct
- [ ] `Default` impl present
- [ ] `saturating_add`/`saturating_mul` — no overflow risk
- [ ] `EPISTEMIC TIER: T2` in file header comment
- [ ] No `--all-features` flag (hip/rocblas require ROCm hardware)

**Step 4 — Stage and commit:**
```bash
git add aegis-cl-psi/src/<gate_A>.rs aegis-cl-psi/src/<gate_B>.rs aegis-cl-psi/src/lib.rs
git commit -m "Gates <N>-<M>: <short description>

Gate <N>: <LogType> — <what it tracks>.
  <key formula>
  entry_hash = SHA-256(<field list>).
  Aggregates: <list>. <N_tests> tests.

Gate <M>: <LogType> — <what it tracks>.
  <key formula>
  entry_hash = SHA-256(<field list>).
  Aggregates: <list>. <N_tests> tests.

Total: <count> tests passing.

https://claude.ai/code/session_01WvFyntZArqThRgLczRutuM"
```

**Step 5 — Update CLAUDE.md:**
- Gates complete: `N` → `N+2`
- Test count: `(XXXX tests)` → updated count
- Gate module count: `XXX gate modules` → updated

**Step 6 — Push:**
```bash
git push -u origin claude/aegis-setup-Lx7Ji
```
NEVER push to any other branch without explicit operator permission.

---

### For TypeScript gates (sovereign-omega-v2):

**Gate 8 (mandatory before every commit):**
```bash
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build
```
Assert: all pass, 0 type errors, build artifact produced.

**Hash integrity:**
```bash
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs
```
Assert: exits 0. gate.py / dna.py / router.py hashes match CLAUDE.md.

**Commit:**
```bash
git add <specific files — never git add -A>
git commit -m "Gate <N>: <title>

<description>

https://claude.ai/code/session_01WvFyntZArqThRgLczRutuM"
```

---

## Reporting Format

```
SHIP REPORT:
  Gate tests: PASS (<N> tests)
  Full suite: PASS (<total> tests, 0 failed)
  Invariant check: PASS / VIOLATIONS: <list>
  Hash integrity: PASS / FAIL
  Committed: <commit hash>
  Pushed: YES / NO
  CLAUDE.md updated: YES / NO
```
