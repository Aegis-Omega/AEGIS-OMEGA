# Contributing to AEGIS--

Thank you for your interest in AEGIS--. This project follows strict gate-based development. Please read this guide before opening a PR.

## Prerequisites

| Tool | Version |
|------|---------|
| Node | ≥ 20.x |
| Rust | ≥ 1.75 (stable) |
| Python | ≥ 3.11 |
| Docker | ≥ 24.x (optional, for quick-start path) |

## The Gate Discipline

Every change must satisfy **Gate 8** before it can be merged:

```bash
# TypeScript governance runtime (Gate 8 — mandatory before every commit)
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build

# Rust gossip fabric
cd aegis-cl-psi && cargo test

# Rust seven-pillar runtime
cd aegis-runtime && cargo test
```

If any of the above fails, your PR will not be reviewed.

## Determinism Rules (non-negotiable)

When touching governance, ledger, or hash-chain code:

- ❌ Never use `HashMap` / `HashSet` — use `BTreeMap` / `BTreeSet`
- ❌ Never use `f64` inside hash inputs — use `value.to_bits().to_be_bytes()`
- ❌ Never call `Date.now()` outside `src/event/uuid.ts`
- ❌ Never use `JSON.stringify` for integrity — use `canonicalizeJCS`
- ✅ Always `deepFreeze()` records after construction (TypeScript)
- ✅ Always use `saturating_add` / `saturating_mul` (Rust)
- ✅ All imports use `.js` suffix (ESM)
- ✅ Sequence numbers must be strictly monotone

## Frozen Files (never modify without guardian approval)

These three files are SHA-256 verified on every session start. Any change causes a T0 abort:

| File | Purpose |
|------|---------|
| `sovereign-omega-v2/python/gate.py` | Constitutional gate validation |
| `sovereign-omega-v2/python/dna.py` | Governance DNA encoding |
| `sovereign-omega-v2/python/router.py` | Multi-model routing |

Verify integrity before any session: `cd sovereign-omega-v2 && node scripts/verify-hashes.mjs`

## Development Workflow

1. Fork the repository
2. Create a branch: `gate-<N>-<short-description>` (e.g. `gate-606-bls-signatures`)
3. Implement the change
4. Add unit tests — each gate module requires 10–30 tests
5. Run the full test suite (Gate 8 above)
6. Commit with the test count in the message:

```
gate-606: add BLS signature verification to gossip layer

Tests: +18 (total now 9766)
```

7. Open a PR using the template; assign reviewers per CODEOWNERS

## Epistemic Tier System

Tag every new module with its tier in the header comment:

| Tier | Meaning |
|------|---------|
| T0 | Mechanically proven — deterministic, byte-identical |
| T1 | Empirically validated — rules hold across observed evidence |
| T2 | Engineering hypothesis — deterministic but not yet proven optimal |
| T3 | Research conjecture — plausible, no empirical validation |

T4/T5 constructs are blocked from `src/` — they belong in `docs/` only.

## Questions

- **Bug reports** → [GitHub Issues](https://github.com/Aegis-Omega/AEGIS--/issues)
- **Design questions** → [GitHub Discussions](https://github.com/Aegis-Omega/AEGIS--/discussions)
- **Security vulnerabilities** → see [SECURITY.md](SECURITY.md)
