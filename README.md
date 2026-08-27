# AEGIS-Ω

**A proof-carrying constitutional AI runtime** — governed transitions can be bound to independently observed effects, replay evidence, and tamper-evident receipts.

[![CI](https://img.shields.io/github/actions/workflow/status/Aegis-Omega/AEGIS-OMEGA/ci.yml?branch=main&label=CI%20CEREMONY)](https://github.com/Aegis-Omega/AEGIS-OMEGA/actions)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](LICENSE)
[![Live](https://img.shields.io/badge/live-aegisomega.com-C8A96E)](https://aegisomega.com)

> Designed and built by Tarik Skalić · Bihać, Bosnia-Herzegovina · AGPL-3.0

---

## What it is

AEGIS-Ω doesn't merely *describe* governance — its wired runtime paths enact it mechanically. The verified platform-start vertical slice binds an authority decision, execution attempt, independent pre/post observations, effect verification, and complete verification to one transition identity. Replayable subsystems use canonical SHA-256 lineage and fail when reconstruction diverges.

This claim is deliberately scoped. Not every module or model response in the repository is on that live authority path; tested-only and dormant components are classified in [`REPO_MAP.md`](REPO_MAP.md).

One law governs the whole system:

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

*No authoritative claim may exceed the weakest verified transition required to establish it.*

## Verified live action boundary

The current evidence-bearing platform path is:

```text
Intent → DecisionReceipt → ExecutionReceipt → EffectObservation
       → VerifyEffect → EffectReceipt → CompleteVerification
```

For `aegis_start_execution`, the runtime performs an independent pre-observation, the POST attempt, and two independent GET observations. All observations must bind to the same revision, contract, execution identity, and transition. A successful POST response alone cannot establish an effect, and read-only observations do not consume execution quota.

Exact hosted evidence for the integration candidate is recorded on [PR #334](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/334). The verified candidate remains a draft until separately admitted and merged; GREEN CI is not a production-deployment receipt.

---

## See it prove itself (30 seconds)

Don't take "verifiable" on faith — run it. No build step, no API keys, Python stdlib only:

```bash
# 1. A genomics variant-caller whose result is a reproducible, tamper-evident hash
python3 genomics/test_replay_proof.py        # 3 invariants → exit 0

# 2. The SAME governance envelope on a regulated loan-decision audit, plus a
#    byte-identical cross-check proving it's literally the same primitive
python3 verifiable/test_generality.py         # exit 0

# 3. The genomics certificate rebuilt from GENESIS in Python, Node.js AND Rust —
#    three independent RFC 8785 canonicalizers, one identical SHA-256
bash   verifiable/cross_language/verify.sh    # Python == Node == Rust

# 4. The whole substrate certifies itself in one reproducible session hash
python3 verifiable/certify_all.py --twice
```

Every run — every language, every machine — lands on the same fingerprint:

```
genomics terminal     f8cb0093b9b7447cc44d7386f1305f427dc7eb887a23407f9b67522b8f5db8f1
session certificate   9b360cad56518c8a5a8c42ac2c97fe4bb17948bf1778b513f7c7db041ad6d142
```

CI re-proves this on **every push, across Ubuntu (x86-64) and macOS (arm64)** — the
terminal hash is pinned, so a divergence on any platform fails the build. Flip one base
in the input and all the hashes move together; edit a stored result after the fact and
`certify()` names the tampered stage. That is the whole thesis in runnable form:
**determinism lives in the governance envelope, not the model** — which is exactly what
turns a stochastic AI output into auditable evidence.

Honest scope: the caller and scorecard are toy (tier **T2**) — the proven claim is the
*envelope* (reproducibility + tamper-evidence + cross-runtime replay), not domain
accuracy. Details: [`genomics/README.md`](genomics/README.md) ·
[`verifiable/README.md`](verifiable/README.md).

---

## Quickstart

```bash
git clone https://github.com/Aegis-Omega/AEGIS-OMEGA
cd AEGIS-OMEGA

# Orient: branch · drift from main · membrane · live status
bash scripts/ground-truth.sh

# TypeScript governance runtime — Gate 8 (run before every commit)
cd sovereign-omega-v2 && npm ci
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
| `genomics/` | Domain proof | Replay-verifiable variant caller + a governed, prompt-cached AI interpretation folded into the same hash chain |
| `verifiable/` | Envelope + proofs | Domain-agnostic RFC 8785→SHA-256 lineage, a second (regulated-decision) domain, cross-language replay (Py/Node/Rust), self-certifying session cert |
| `packages/aegis-interface/` | Interface compiler | RFC 0001/0005 — deterministic WIT→IR→{Rust, TS, Python} with a cross-language equivalence gate |
| `packages/aegis-py/` | SDK + CLI | `AegisClient` / `AsyncAegisClient` / `aegis` CLI for the Platform API |
| `harness/sdk/proof_carrying_platform_execution.py` | Action boundary | Authority decision → bridge execution → independent effect observations → complete verification |
| `harness/sdk/platform_effect_adapter.py` | Effect observer | Revision-bound readback adapter; never trusts the POST response as effect proof |
| `packages/shared/` | Shared infra | Inference router (DashScope→Ollama→Claude→CL-Ψ), constitutional-ai, payment tokens |
| `clients/gemma-holon/` | Edge holon | Gemma-4E4B on-device constitutional validation node + Ogemma Mythos gates |
| `hub/` | Web | [aegisomega.com](https://aegisomega.com) — live hash-chained metacognitive loop + WebGPU Φ-field |
| `platform-picker/` · `hook-generator/` · `content-calendar/` | Products | Commercial creator tools ($19 each) |
| `supabase/functions/` | Edge functions | `verify-paypal`, `notify` |

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
| TypeScript — `sovereign-omega-v2` | 4,130 passing on PR #334 exact-head Gate 8 |
| Rust — `aegis-cl-psi` | 7,178 |
| Rust — `aegis-runtime` | 133 |
| Python — `aegis-interface` (RFC 0001/0005) | 50 |
| Python — authorization/effect-chain targeted regression | 84 |
| Python — proof-trace targeted regression | 31 |

```bash
cd aegis-cl-psi   && cargo test          # never --all-features (ROCm-gated)
cd aegis-runtime  && cargo test
cd packages/aegis-interface && python -m pytest
```

**Scale:** ~260k lines of source across Rust / TypeScript / Python / WGSL (~352k tracked total), ≈11,900 tests, plus TLA+ and Coq-style formal artifacts. Reproducible metrics: [`docs/PROOF.md`](docs/PROOF.md).

**CI:** the CEREMONY gate is a BFT quorum of 6 jobs at threshold 1/φ ≈ 0.618 — fewer than 4/6 passing blocks merge.

### Agent Dispatch status

`.github/workflows/agent-dispatch.yml` is an optional external integration boundary. It dispatches only when the repository variable `PROXY_URL` identifies an explicitly configured constitutional proxy. Without that variable, the workflow completes successfully with `Status: DISABLED` and proves that no network request or agent execution was attempted.

The workflow listens to completion of the canonical `⊕ AEGIS-Ω Constitutional Automaton`, PR events, issues, and `@aegis-agent` comments. Configuring `PROXY_URL` establishes routing, not trust: the receiving proxy still owns authorization, execution, effect verification, and admission.

GitHub evaluates `workflow_run` triggers from the default branch. Therefore the corrected post-CI trigger becomes live only after this workflow revision is admitted to `main`; on the draft PR, the `pull_request` path is the executable proof that the disabled-state receipt works. See [GitHub's event-trigger rules](https://docs.github.com/actions/using-workflows/events-that-trigger-workflows#workflow_run).

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
- **Agent dispatch deployment** — source wiring is present, but external dispatch remains intentionally disabled until `PROXY_URL` is configured and the receiving proxy is independently verified.
- **Replay state explosion** — the full event log is not prunable without the lineage compactor.

---

## License

AGPL-3.0-or-later · Copyright © 2025–2026 Tarik Skalić ([tarikskalic33@gmail.com](mailto:tarikskalic33@gmail.com))

Free to use, study, modify, and distribute. Derivative works must release source under the same terms.

---

*A finite automaton remembers its state. A hash-chained automaton can prove it remembered correctly.*
