---
name: constitutional-audit
description: Live constitutional health check — chains /node, /resonance, /catalog, /health, frozen-file hashes, and Gate 8 test count into a single signed status report. Run when you need to know if the full AEGIS stack is constitutionally sound before a commit, deploy, or major evolution gate.
---

# Constitutional Audit Skill

## Trigger conditions

- User asks for a constitutional health check or system status
- Before any `git push` to main/production branches
- When `T0_verdict` may be in question (after bridge restarts, after epoch resets)
- After any modification to `bridge.py`, `core_matrix.py`, or `aegis-runtime/src/`
- When the user types `/constitutional-audit`

## Behavior

Run the following chain in sequence. Stop and report on first failure.

### Step 1 — Bridge liveness
```bash
curl -sf http://localhost:7890/health
```
Expected: `{"status": "OK", "router_sealed": true}`. If bridge is offline, start it:
```bash
cd sovereign-omega-v2/python && python bridge.py &
sleep 2
```

### Step 2 — T0 Verdict Gate (Autonode)
```bash
curl -sf http://localhost:7890/node | python3 -m json.tool
```
Assert: `t0_verdict == true`, `corruption_count == 0`, `drift_risk < phi_threshold (0.618…)`

### Step 3 — Resonance Monitor (Gate 222)
```bash
curl -sf http://localhost:7890/resonance | python3 -m json.tool
```
Assert: `is_certified == true`, `resonance_depth == 4`, `resonance_coefficient > 5.0`

### Step 4 — Cognitive Triad Catalog
```bash
curl -sf http://localhost:7890/catalog | python3 -m json.tool
```
Assert: `catalog_hash == "b93f7af999e72bc71512e4e8fd8402c9"`, `cognitive_triad == "ALL 3 PRESENT"`

### Step 5 — Frozen File Hashes
```bash
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs
```
Assert: gate.py, dna.py, router.py all `OK`.

### Step 6 — Gate 8
```bash
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build
```
Assert: all tests pass, 0 type errors, build clean.

### Step 7 — Rust Suite
```bash
cd aegis-runtime && cargo test
```
Assert: all tests pass.

## Reporting format

```
CONSTITUTIONAL AUDIT: [PASS|FAIL]
  T0 verdict    : [PASS|FAIL] (corruption=N, drift=0.NNNN)
  Resonance     : [CERTIFIED|BREACH] (depth=N/4, coeff=N.NNN)
  Catalog hash  : [b93f7af…|MISMATCH]
  Frozen files  : [OK|VIOLATED — gate.py|dna.py|router.py]
  Gate 8        : [PASS — NNNN tests|FAIL]
  Rust suite    : [PASS — NN tests|FAIL]
  
Root law: AdaptivePower(T) ≤ ReplayVerifiability(T) — [SATISFIED|EXCEEDED]
```

## Critical invariants

- NEVER skip Step 5 (frozen file hashes) — these files are constitutional law
- NEVER declare PASS if any step fails — partial passes are failures
- Report corruption_count exactly — never round or suppress
- catalog_hash must match `b93f7af999e72bc71512e4e8fd8402c9` exactly — any mismatch is a T0 violation
