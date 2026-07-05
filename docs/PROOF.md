# AEGIS-Ω — Proof / Verification Sheet

A receipt anyone can reproduce in minutes. Every number below was measured
directly from the tracked repository (excluding `node_modules` and build output),
not asserted. Commands are included so you can confirm each figure yourself.

---

## Scale

| Metric | Value |
|--------|-------|
| Total tracked lines (all text, excl. `node_modules`/build) | **~352,600** |
| Source code (Rust + TS + TSX + Python + JS + MJS + WGSL) | **~260,800** |
| Tracked files | **1,715** |
| Languages in source | Rust, TypeScript, Python, WGSL (WebGPU), JS, + formal specs |

### Lines by language (measured)

| Lines | Type | Role |
|-------|------|------|
| 137,692 | `.rs` | Rust — CL-Ψ inference gates, Seven-Pillar runtime, verifiers |
| 80,447 | `.ts` | TypeScript governance runtime |
| 26,668 | `.py` | Python bridge / agents |
| 13,225 | `.tsx` | UI (hub, cockpit, studio) |
| 1,563 | `.js` | + 922 `.mjs` |
| 1,015 | `.wgsl` | WebGPU shaders (Φ-field engine) |
| 711 | `.sql` | |
| 466 | `.tla` | **TLA+ formal specification** |
| 349 | `.v` | **Coq-style proof artifacts** |
| 346 | `.tf` | Terraform infra |

```bash
# Reproduce total + per-language counts:
git ls-files | grep -v node_modules | grep -vE '/(dist|build|target|\.next|out)/' \
  | xargs wc -l | tail -1
for e in rs ts tsx py js mjs wgsl tla v sql; do
  printf "%-5s " ".$e"; git ls-files "*.$e" | grep -v node_modules | xargs wc -l | tail -1
done
```

---

## Tests

| Suite | Count | Source |
|-------|-------|--------|
| Rust `#[test]` / `#[tokio::test]` | **7,657** | measured (pattern count) |
| TypeScript/TSX `it()` / `test()` | **4,092** | measured (pattern count) |
| Python `def test_*` | **200** | measured (pattern count) |
| **Total** | **≈ 11,949** | |

Documented per-suite figures (from `CLAUDE.md` / `README.md`): TS 4,076 ·
`aegis-cl-psi` 7,178 · `aegis-runtime` 133 · `aegis-interface` 50.

```bash
git ls-files '*.rs'        | xargs grep -hE '^\s*#\[(tokio::)?test\]' | wc -l
git ls-files '*.ts' '*.tsx'| grep -v node_modules | xargs grep -hE '^\s*(it|test)\(' | wc -l
git ls-files '*.py'        | xargs grep -hE '^\s*def test_' | wc -l
```

---

## Determinism / replay verification (the core claim)

Zero-divergence replay is enforced by code, not just described:

| Artifact | Path |
|----------|------|
| Cross-language CCIL verifier (Python kernel ↔ JS) | `aegis-ccil-verifier/aegis_verifier.py`, `aegis-ccil-verifier/canonical.js` |
| Rust edge verifier | `aegis-cl-psi/src/edge_verifier.rs` |
| Metacognitive replay | `.claude/metacog/replay.mjs` |
| Frozen-file membrane (SHA-256) | `sovereign-omega-v2/scripts/verify-hashes.mjs` |
| TLA+ specification | `*.tla` (466 lines) |

Determinism invariants enforced throughout: `BTreeMap`/`BTreeSet` only,
`to_be_bytes` for all hash inputs (no `f64`), RFC 8785 canonicalization
(`canonicalizeJCS`), `deepFreeze` after construction, `saturating_*` arithmetic.

```bash
# Reproduce the proofs end-to-end:
cd sovereign-omega-v2 && bash scripts/proof-demo.sh      # six constitutional proofs
node scripts/verify-hashes.mjs                            # frozen membrane (exit 0)
cd ../aegis-cl-psi   && cargo test                        # Rust gate suite
cd ../aegis-runtime  && cargo test                        # Seven-Pillar runtime
```

---

## Root law

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

No part of the system can do more than it can prove it did. φ-convergence:
`MUTATION_RATE_LIMIT = DEFAULT_QUORUM_THRESHOLD = (√5−1)/2 ≈ 0.6180339887`.

---

*Measured 2026-06-30 from the tracked tree. Re-run the commands above to verify
any figure independently.*
