---
name: rwkv7-wave-logic
description: Invoked when the user asks about RWKV-7, wave-logic inference, O(1) memory transformers, linear attention, or replacing Transformer KV-cache with recurrent state. Source: AEGIS-SOVEREIGN OS Blueprint, tier T2.
---

# RWKV-7 Wave-Logic Engine

**Epistemic Tier: T2** — engineering hypothesis. O(1) memory claim is analytically derivable from the linear attention formulation; production benchmark on AEGIS workloads is pending.

**Corpus Lineage:** `corpus_lineage_hash: pending-drive-access` · Source: AEGIS-SOVEREIGN OS Blueprint (ARBITRATION: admitted T2, T4/T5 "planetary autonomy" framing quarantined to FUTURE_PHASES.md)

---

## Constitutional Claim

RWKV-7 provides O(1) memory per inference token via a linear recurrence formulation that replaces the O(n) KV-cache of Transformer attention, making it viable for long-horizon AEGIS governance calls without the replay-safety risk introduced by unbounded KV accumulation.

---

## Key Invariants

- **O(1) memory per token** — RWKV-7 maintains a fixed-size recurrent state; memory cost does not grow with sequence length (unlike Transformer KV-cache which is O(n × d_head × n_heads))
- **Wave-logic recurrence** — each timestep applies a learned diagonal+low-rank state update; the wave metaphor denotes the signal-propagation structure, not a claim about wave physics
- **Replay-safe formulation** — the recurrent state is deterministically computable from the input token sequence alone, making replay reconstruction possible without storing the full context window
- **Transformer parity on long tasks** — RWKV-7 matches Transformer quality on tasks ≥4K tokens where KV-cache overhead dominates; below 512 tokens the advantage is marginal
- **No alignment claim** — replacing Transformer attention with RWKV-7 does not change the constitutional audit chain; every inference call still produces a `ConstitutionalResponse` with `chain_hash` and `is_replay_reconstructable: true`

---

## AEGIS Integration Points

| Component | How RWKV-7 applies |
|-----------|-------------------|
| `src/api/claude-client.ts` | Drop-in model swap — `ConstitutionalClaudeClient` is model-agnostic; RWKV-7 endpoint would plug into the same hash-audit chain |
| `python/bridge.py` | Bridge `/claude` endpoint routes to whichever model is configured via `AEGIS_INFERENCE_MODEL` env var |
| `packages/shared/lib/inference-router.ts` | `cl-psi` backend in the router chain is the natural slot for a local RWKV-7 process |

---

## Tier Promotion Criteria (T2 → T1)

≥3 independent benchmarks on AEGIS governance call distributions (replay/audit/calibration tasks) demonstrating:
1. Memory consumption ≤ O(1) empirically (constant RSS at 1K / 4K / 16K token inputs)
2. Quality parity with `claude-sonnet-4-6` on tier-classification and hash-audit tasks
3. Replay determinism: identical `chain_hash` across 3 identical inference runs

---

## Source

Admitted T2 engineering claim from corpus ARBITRATION (corpus-ingestion pipeline). Quarantined T4/T5 framing: "planetary autonomy / sovereign OS" → `sovereign-omega-v2/docs/FUTURE_PHASES.md`.
