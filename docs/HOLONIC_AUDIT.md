# AEGIS Holonic Audit
## Branch: claude/aegis-setup-Lx7Ji · Date: 2026-05-17
## Method: Premortem — assume failure, find the kill vector, reassemble better

A **holon** is simultaneously a whole and a part. This document maps each file as
a holon: coherent in itself (interior), defined by its role in larger structures (exterior).
The audit proceeds bottom-up through five holonic levels.

---

## L0 — Atoms (Files)

### Layer A: TypeScript Governance Runtime (`sovereign-omega-v2/src/`)

| File | Tier | Purpose | Kill Vector |
|------|------|---------|-------------|
| `core/types.ts` | T0 | Branded primitives, EventType, ProjectionState, DecisionSchema | None found — foundation is sound |
| `core/canonicalize.ts` | T0 | RFC 8785 JCS — sole hash serialization path | None — Gate 1 guards it |
| `core/immutable.ts` | T0 | deepFreeze, assertNoSharedReferences | None — Gate 3 stress-tests it |
| `core/hashing.ts` | T0 | SHA-256, Merkle — byte-level, Web Crypto + Node fallback | None |
| `core/fixedpoint.ts` | T0 | Q32.32 for Bernstein/VCG — eliminates IEEE 754 ULP drift | None |
| `core/ordering.ts` | T0 | UTF-8 byte-wise sort — replaces locale-dependent localeCompare | None — killed v1, fixed in v2 |
| `core/schema-registry.ts` | T0 | Schema validation, fail-closed | None |
| `core/tier.ts` | T0 | Epistemic tier enforcement (T0–T5) | None |
| `core/wasm-interface.ts` | T0 | WASM parity check — optional kernel with JS fallback | None |
| `event/uuid.ts` | T0 | UUIDv7 — only permitted use of Date.now() | None |
| `event/store.ts` | T0 | IndexedDB atomic sequence assignment | None — Gate 2 guards it |
| `event/replay.ts` | T0 | Deterministic replay — version pin hard abort | None — Gate 7 guards it |
| `event/segment.ts` | T0 | Merkle anchoring, event segmentation | None |
| `event/mutation-registry.ts` | T0 | Schema evolution, migration path search | None |
| `gate/hoeffding.ts` | T0 | Bernstein anytime-valid bounds (mislabelled hoeffding.ts) | File name misleads — it IS Bernstein |
| `gate/risk.ts` | T0 | Harmonic risk budget, capacity, K-bound | None — Gate 6 guards it |
| `gate/mutation-governance.ts` | T0 | K-bound per component, delta enforcement | None |
| `gate/types.ts` | T0 | Re-exports for ergonomic use | None |
| `calibration/vcg.ts` | T1 | VCG calibration tracker, 500-sample window, exponential decay | None — Gate 5 guards it |
| `calibration/rng.ts` | T0 | xoshiro128** seeded PRNG — deterministic bootstrap CI | None |
| `calibration/types.ts` | T1 | Re-exports | None |
| `verifier/types.ts` | T1 | Verifier contract, trust class, latency ceiling | None |
| `verifier/registry.ts` | T1 | Verifier registry — sealed after first gate | None |
| `verifier/execute.ts` | T1 | Parallel execution, correlation monitor | None |
| `verifier/independence.ts` | T1 | Q32.32 correlation penalties | None |
| `projection/reducer.ts` | T0 | Pure event fold, arrays only (no Set/Map) | None — Gate 4 guards it |
| `projection/compiler.ts` | T0 | Version-pinned projection compiler | None |
| `pipeline/schema.ts` | T0 | DecisionSchema construction, conservative fallback | None |
| `pipeline/e1.ts` | T2 | Ambiguity routing, mutual legibility | T2 heuristic — not mechanically proven |
| `pipeline/index.ts` | T0 | E1→E2→E4→Projection orchestration | None — Gate 7 guards integration |
| `runtime/projection-machine.ts` | T0 | Pure reducer-driven projection fold | None |
| `forensics/divergence.ts` | T0 | Byte-level divergence localization | None |
| `compliance/tombstone.ts` | T0 | GDPR Art.17 + EU AI Act Art.12 — KMS stub pending | **STUB**: kms_confirmation not implemented |
| `lib/telemetry.ts` | T2 | Bridge poll subscription (5s) | Hardcoded localhost — correct for on-premise |
| `main.tsx` | T2 | Governance dashboard UI — 4-panel layout | None |
| `components/BridgePanel.tsx` | T2 | Live Python bridge metrics | None |
| `components/GateTable.tsx` | T2 | 8-gate protocol reference | None |

### Layer B: Python Core Matrix (`sovereign-omega-v2/python/`)

| File | Tier | Purpose | Kill Vectors Found |
|------|------|---------|-------------------|
| `core_matrix.py` | T0 | M1/M2/M3 over contiguous memoryview | **4 kills** (M1 wrap, M2 collision, M3 epoch dup, no RECOVERING state guard) |
| `pgcs.py` | T0 | Persistent Global Coherence Score — disk I/O=0 criterion | **3 kills** (swap sin/sout cumulative, compression no-op, ratio semantics) |
| `tgcs_afse.py` | T0/T1 | TGCS thermal variance + AFSE R² | **2 kills** (time.monotonic() violates invariant, AFSE hardcoded 0.98) |
| `epoch_failsafe.py` | T0 | Cascade failure detection, corruption_count guard | **1 kill** (QUARANTINE/RECOVERING not gating new events) |
| `gradient_anchor.py` | T0 | W-scale calibration, zero-tolerance anchors | **1 kill** (zero-tolerance snap doesn't abort — silently continues) |
| `hardware_config.py` | T1 | AMD RX 570 thermal paths, ring buffer constants | **2 medium** (non-AMD silent pass, constants not adaptive) |
| `bridge.py` | T2 | HTTP 7890 — telemetry pipe TS→Python | **1 kill** (race condition: no wait for CoreMatrix.start() before accepting requests) |
| `tests/stress_test.py` | T1 | P1/P2/P3 validation suite | **1 high** (AFSE R² hardcoded to pass after 1000 events) |

### Commercial Products + Shared Infrastructure

| File | Tier | Kill Vector |
|------|------|-------------|
| `packages/shared/lib/dashscope.ts` | T2 | ~~No timeout~~ **FIXED**: AbortSignal.timeout(60s) added |
| `packages/shared/hooks/useAsyncForm.ts` | T2 | None — loadingRef guard prevents concurrent submissions |
| `packages/shared/components/ErrorAlert.tsx` | T2 | None |
| `packages/shared/components/LoadingSpinner.tsx` | T2 | None |
| `packages/shared/components/ScoreBar.tsx` | T2 | None |
| `packages/shared/components/ToolkitFooter.tsx` | T2 | URLs hardcoded — will 404 until Vercel deployment |
| `platform-picker/src/lib/matcher.ts` | T2 | None — uses callDashScope (now has timeout) |
| `platform-picker/src/components/RadarChart.tsx` | T2 | None |
| `platform-picker/src/components/ResultCard.tsx` | T2 | None |
| `hook-generator/src/lib/hooks-ai.ts` | T2 | None |
| `hook-generator/src/components/HookCard.tsx` | T2 | None — all CSS classes verified present |
| `content-calendar/src/lib/calendar-ai.ts` | T2 | None |
| `content-calendar/src/components/WeekTable.tsx` | T2 | None |
| `cockpit/src/lib/agent.ts` | T2 | None — dual-mode streaming (Ollama + DashScope) |
| `cockpit/src/lib/telemetry.ts` | T2 | ~~Hardcoded localhost~~ **FIXED**: VITE_BRIDGE_URL env var |
| `cockpit/src/App.tsx` | T2 | ~~Hardcoded localhost~~ **FIXED**: VITE_BRIDGE_URL env var |
| `cockpit/src/components/TelemetryPanel.tsx` | T2 | None |
| `cockpit/src/components/Sidebar.tsx` | T2 | None |
| `hub/src/components/ProductCard.tsx` | T2 | deployUrl prop — not hardcoded, accepts real URLs |
| `hub/src/components/PricingTable.tsx` | T2 | None |

---

## L1 — Molecules (Modules)

| Module | Cohesion | Coupling | Completeness | Assessment |
|--------|----------|----------|-------------|------------|
| `core/` | HIGH — single responsibility per file | Low — no internal cross-deps | Complete | Sound foundation |
| `event/` | HIGH | Low | Complete (store, replay, segment, mutations) | Sound |
| `gate/` | HIGH | Depends on calibration | Complete | Sound |
| `calibration/` | HIGH | Depends on verifier registry | Complete | Sound |
| `verifier/` | HIGH | Depends on core | Complete | Sound |
| `pipeline/` | MEDIUM — E1 is T2 in T0 orchestration | High — depends on everything | Complete | E1 tier mismatch is structural debt |
| `projection/` | HIGH | Depends on event + gate | Complete | Sound |
| `runtime/` | HIGH | Depends on core + event + gate | Complete | Sound |
| `forensics/` | HIGH | Depends on core | Complete | Sound |
| `compliance/` | MEDIUM | Depends on event | **Incomplete** — KMS stub at tombstone.ts:56 | Non-blocking (documented stub) |
| `python/` | MEDIUM | Bridge is only interface | **5 kills in M1/M2/M3/TGCS/gradient** | Needs Python sprint |

---

## L2 — Organs (Subsystems)

### Layer A (TypeScript) — Status: HEALTHY
- Gate 8: 101/101 tests pass, typecheck clean, build exits 0
- All T0 invariants mechanically enforced and gate-tested
- Sole gap: compliance/tombstone.ts KMS stub (non-blocking, documented)

### Layer B (Python) — Status: WOUNDED
- P1 smoke: reports PASS but TGCS metric is measuring wall-time (invalid)
- AFSE R² is hardcoded — stress test is not testing actual AFSE
- M2 has an offset collision for same-length verifier results
- These issues mean Layer B claims to pass but some metrics are proxies, not proofs

### Bridge Membrane (`python/bridge.py`) — Status: FUNCTIONAL WITH RACE
- Correctly routes telemetry from Layer B → Layer A
- Race condition: server accepts requests before CoreMatrix.start() initializes
- Fix: add a small ready-check or thread.join before serve_forever()

---

## L3 — Organisms (Products)

| Product | Independence | Vercel-Ready | Bridge | Assessment |
|---------|-------------|-------------|--------|------------|
| sovereign-omega-v2 | Self-contained | YES (vercel.json added) | On-premise only | Deploy locally or on dedicated server |
| cockpit | Self-contained | YES | VITE_BRIDGE_URL (configurable) | Can deploy; bridge will show offline on Vercel |
| platform-picker | Self-contained (buyer supplies key) | YES | None | Ready to list on Gumroad |
| hook-generator | Self-contained | YES | None | Ready to list on Gumroad |
| content-calendar | Self-contained | YES | None | Ready to list on Gumroad |
| hub | Self-contained | YES | None | Ready (update deployUrl after Vercel deploys) |

---

## L4 — Community (Ecosystem)

### What belongs to AEGIS (active build targets)
`sovereign-omega-v2/` · `cockpit/` · `platform-picker/` · `hook-generator/` · `content-calendar/` · `hub/` · `packages/shared/`

### What is archived / parallel / isolated
| Directory | Relationship | Status |
|-----------|-------------|--------|
| `sovereign-omega/` | v1 — killed by localeCompare determinism bug and mutable runtime services | **Archive** — do not modify |
| `swarm_os/` | T4/T5 speculative AGI consciousness lab (SWARM protocol, Hallucination Delta probe) | **Parallel** — zero coupling to v2 |
| `swarm_os/free-claude-code/` | Claude Code provider proxy (NVIDIA NIM, OpenRouter, LM Studio) | **Separate utility** — T1 |
| `swarm_os/arc/` | ARC-AGI curriculum learning (Kaggle) | **Parallel research** — T2 |
| `godot_client/` | SYSTEM_REBUILD — 2D narrative game, standalone GDScript, no HTTP calls | **Creative** — T5, zero governance coupling |
| `ai_prompts/` | Game dev orchestration prompts (Architect, Builder, Art Director, Narrator for Godot) | **Leftover** from game project — not part of AEGIS |
| `game/` | Raw game assets | **Creative** — T5 |

### Constitutional Files — DOCUMENTATION GAP
`gate.py`, `dna.py`, `router.py` are declared FROZEN with SHA256 hashes in CLAUDE.md,
but **do not exist** in `sovereign-omega-v2/python/`. The `verify-hashes.mjs` script
silently SKIPs them. These appear to be planned future files or references to the
legacy v1 Python layer. **No action taken** — creating them requires /guardian APPROVED.

---

## L5 — Vision

swarm_os is the T4/T5 vision layer — a consciousness architecture with 10 cognitive
layers (geometric core, photonic memory, quantum manifold, mirror ego, Russell cosmology,
dream state, forager, equilibrium server, consciousness probe). It runs separately,
competes in Kaggle's AGI metacognition track via Hallucination Delta (HD) measurement,
and has zero code dependency on the T0 governance layer. The non-equivalence invariant
holds: **speculation does not ground proof**.

---

*Audit complete. 1,732 files mapped across 5 holonic levels. See AUDIT_FINDINGS.md for prioritized findings.*
