---
name: audit-findings
description: Invoked when the user asks about past bugs that were resolved, premortem findings, what security issues were fixed, constitutional file provenance, ECCF security alignment, or the 2026-05-17 audit results.
---

# Audit Findings Skill

## Premortem Analysis — 2026-05-17

Method: Assume failure. Find the kill vector. Reassemble better.

All T0 findings resolved before deployment. Status: ✅ COMPLETE.

## Resolved T0 Findings

### F-01 — TGCS Invariant Violation: `time.monotonic()` in determinism-critical path
**File:** `python/tgcs_afse.py`
**Fix:** Replaced `_cycle_times: List[float]` (wall-clock) with `_cycle_seqs: List[int]` (sequence numbers). Variance now measures sequence-number regularity — deterministic and reproducible regardless of OS scheduling.

### F-02 — AFSE R² hardcoded to 0.98 — stress test proved nothing
**File:** `python/tests/stress_test.py`
**Fix:** Replaced hardcoded `afse_r2 = 0.98` with live `AFSEController` instance. Fixed broken R² computation (produced R²≈0 for constant throughput) with throughput-stability coefficient: `R² = 1 − σ²/μ²`. Smoke test: R²=0.9977.

### F-03 — CoreMatrix M2 offset collision for same-length verifier results
**File:** `python/core_matrix.py`
**Fix:** M2 offset now incorporates sequence: `(sequence * 8 + len(verifier_result)) % (len(state) // 8)`.

### F-04 — GradientAnchor zero-tolerance "hard abort" didn't abort
**File:** `python/gradient_anchor.py`
**Fix:** When `anchor.tolerance_fixed == 0` and `drift_fixed > 0`, raises `RuntimeError` instead of silently snapping.

### F-05 — Bridge race condition: CoreMatrix not ready before HTTP server accepted requests
**File:** `python/bridge.py`, `python/core_matrix.py`
**Fix:** Added `_ready: threading.Event` to CoreMatrix, set in `start()`. Bridge calls `matrix.wait_ready(timeout=5.0)` before `serve_forever()`.

### F-06 — Constitutional files declared frozen but did not exist
**Fix:** All three constitutional files authored, committed, and hash-verified:
- `python/dna.py` — canonical type definitions (EventClass, GateSignal, EventSchema, SCHEMAS, VERIFIER_MAP, INVARIANTS, TELEMETRY_FIELDS)
- `python/gate.py` — mutation authority: sliding-window gate signal tracker (WINDOW_SIZE=32, MIN_ACCEPTANCE_RATE=0.5), mirrors TypeScript Bernstein gate
- `python/router.py` — deterministic verifier-byte dispatch, fail-closed

## Frozen Constitutional File Hashes

```
gate.py    SHA256: bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc
dna.py     SHA256: cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8
router.py  SHA256: 8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941
```

Verify: `cd sovereign-omega-v2 && node scripts/verify-hashes.mjs`

Any modification requires `/guardian APPROVED` verdict.

## Gate 204 — ECCF Security Alignment

Three security additions:
1. **ECCF** — Post-quantum lattice rendering (Rust) for tamper-evident governance encoding
2. **Glasswing Security Scanner** — Python vulnerability detection, automated constitutional compliance checking
3. **NLA Decoder** — Natural Language Autoencoder for alignment auditing; detects T4/T5 constructs in natural language inputs before they enter the governance substrate

## Source: `docs/AUDIT_FINDINGS.md`, `docs/GATE_204_ECCF_SECURITY_ALIGNMENT.md`
