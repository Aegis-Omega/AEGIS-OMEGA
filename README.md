# AEGIS-Ω

**A self-governing constitutional AI runtime** — every decision is hash-chained, replay-verifiable, and tamper-evident.

[![CI](https://img.shields.io/github/actions/workflow/status/Aegis-Omega/AEGIS-OMEGA/ci.yml?branch=main&label=CI%20CEREMONY)](https://github.com/Aegis-Omega/AEGIS-OMEGA/actions)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](LICENSE)
[![Live](https://img.shields.io/badge/live-aegisomega.com-C8A96E)](https://aegisomega.com)

> Designed and built by Tarik Skalić · Bihać, Bosnia-Herzegovina · AGPL-3.0

---

## What it is

AEGIS-Ω doesn't *describe* governance — it enacts it mechanically. Every AI response, state transition, and epoch boundary is SHA-256 hash-chained, sequence-numbered, and stored in a tamper-evident ledger that can be replayed from genesis to the same fingerprint. If a replay diverges, that's a detected failure, not a silent one.

One law governs the whole system:

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

*No part of the system can do more than it can prove it did.*

---

## Quickstart

```bash
git clone https://github.com/Aegis-Omega/AEGIS-OMEGA
cd AEGIS-OMEGA

# Orient: branch · drift from main · membrane · live status
bash scripts/ground-truth.sh

# TypeScript governance runtime — Gate 8 (run before every commit)
cd sovereign-omega-v2 && npm install
npm run test && npm run typecheck && npm run build

# Verify the constitutional membrane (must exit 0)
node scripts/verify-hashes.mjs
```

New here? Read [`HANDOFF.md`](HANDOFF.md) (current ground truth) and [`REPO_MAP.md`](REPO_MAP.md) (what's wired vs dormant).

---

## Layout

| Path | Layer | What it is |
|------|-------|-----------|
| `sovereign-omega-v2/` | Governance runtime | TypeScript (canonicalization, martingale, BFT swarm, ledger) + Python bridge (port 7890) |
| `aegis-cl-psi/` | Math fabric | Rust — 422-gate CL-Ψ inference crate, gossip protocol |
| `aegis-runtime/` | Atomic runtime | Rust — Seven-Pillar distributed agent runtime |
| `packages/aegis-interface/` | Interface compiler | RFC 0001/0005 — deterministic WIT→IR→{Rust, TS, Python} with a cross-language equivalence gate |
| `packages/aegis-py/` | SDK + CLI | `AegisClient` / `AsyncAegisClient` / `aegis` CLI for the Platform API |
| `packages/shared/` | Shared infra | Inference router (DashScope→Ollama→Claude→CL-Ψ), constitutional-ai, payment tokens |
| `clients/gemma-holon/` | Edge holon | Gemma-4E4B on-device constitutional validation node + Ogemma Mythos gates |
| `hub/` | Web | [aegisomega.com](https://aegisomega.com) — live hash-chained metacognitive loop + WebGPU Φ-field |
| `platform-picker/` · `hook-generator/` · `content-calendar/` | Products | Commercial creator tools ($19 each) |
| `supabase/functions/` | Edge functions | `verify-paypal`, `issue-token`, `notify` |

---

## Platform API

Governed multi-agent collaboration over HTTP. One API key, one call.

| Endpoint | Purpose |
|----------|---------|
| `GET /platform/status` | Health, contract version, chain validity |
| `POST /platform/collaborate` | 39-department constitutional swarm → hash-chained artifacts + audit verdict |
| `POST /platform/executions` | Async run → SSE stream URL |
| `POST /platform/holon/validate` | External nodes (Gemma, etc.) submit a verdict into the SHA-256 chain |

```bash
curl -X POST https://aegis-vertex.aegisomega.com/platform/collaborate \
  -H "x-api-key: aegis_..." -H "Content-Type: application/json" \
  -d '{"objective":"Enter the EU fintech market","mode":"gtm","live":false}'
```

Get a key at [aegisomega.com/pricing](https://aegisomega.com/pricing) — Explorer (free, 10 runs) · Operator ($49) · Sovereign ($499). Paid via PayPal.

---

## Testing

| Suite | Count |
|-------|-------|
| TypeScript — `sovereign-omega-v2` | 4,076 |
| Rust — `aegis-cl-psi` | 7,178 |
| Rust — `aegis-runtime` | 133 |
| Python — `aegis-interface` (RFC 0001/0005) | 50 |

```bash
cd aegis-cl-psi   && cargo test          # never --all-features (ROCm-gated)
cd aegis-runtime  && cargo test
cd packages/aegis-interface && python -m pytest
```

**CI:** the CEREMONY gate is a BFT quorum of 6 jobs at threshold 1/φ ≈ 0.618 — fewer than 4/6 passing blocks merge.

---

## Determinism invariants

| Rule | Why |
|------|-----|
| `BTreeMap`/`BTreeSet` only — no `HashMap` | Deterministic iteration order |
| No `f64` in hash inputs (`to_be_bytes` only) | IEEE-754 platform variance |
| No `Date.now()` outside `src/event/uuid.ts` | Wall clock is non-deterministic |
| `canonicalizeJCS` (RFC 8785) for all integrity hashing | Cross-platform byte equivalence |
| `deepFreeze()` after construction · `saturating_*` arithmetic | No mutation, no silent overflow |

**φ-convergence:** `MUTATION_RATE_LIMIT = DEFAULT_QUORUM_THRESHOLD = (√5−1)/2 ≈ 0.6180339887` governs the BFT quorum, the entropy ceiling, and the edge-vote weights (Claude 618 / auditor 191 / auditor 191 per 1000).

---

## Frozen constitutional files

Three files define the governance boundary; their SHA-256 hashes are verified at every session start. Modification requires a `/guardian APPROVED` verdict — unauthorized change is a `T0_ABORT`.

```
sovereign-omega-v2/python/gate.py    bbe942b8…
sovereign-omega-v2/python/dna.py     cd30ddd5…
sovereign-omega-v2/python/router.py  8c06ed37…
```

---

## Known open problems

- **GPU nondeterminism** — ROCm HIP kernels vary across hardware; gated behind `#[cfg(feature = "hip")]`, excluded from determinism guarantees.
- **No live peer network** — the gossip layer is implemented and tested but not yet run against a real multi-node mesh.
- **Verifier scalability** — `verify_chain()` is O(n); long chains need segmented verification.
- **Replay state explosion** — the full event log is not prunable without the lineage compactor.

---

## License

AGPL-3.0-or-later · Copyright © 2025–2026 Tarik Skalić ([tarikskalic33@gmail.com](mailto:tarikskalic33@gmail.com))

Free to use, study, modify, and distribute. Derivative works must release source under the same terms.

---

*A finite automaton remembers its state. A hash-chained automaton can prove it remembered correctly.*
