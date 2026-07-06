# AEGIS-Ω — Replay-Verifiable Genomics (worked proof)

**Tier: T2** (engineering hypothesis — computable and demonstrated, not yet clinically validated).
**Constitutional law applied:** `AdaptivePower(T) ≤ ReplayVerifiability(T)`.

## The clinical problem

A variant call that cannot be reproduced byte-for-byte, and whose provenance cannot be
proven un-tampered, is not admissible as a medical-grade result. Standard bioinformatics
pipelines are reproducible only *in spirit*: thread races, hash-map iteration order, and
floating-point non-determinism perturb outputs across runs and machines. When an AI system
sits on top of that stack, the failure mode gets worse — an unverifiable answer is
indistinguishable from a hallucinated one. There is no cryptographic object you can hand a
regulator that says *this exact result came from this exact input, and nothing was edited
after the fact.*

## What this proves

`replay_pipeline.py` runs a structurally faithful variant-calling workflow —
`REFERENCE_LOAD → ALIGN → PILEUP → VARIANT_CALL → ANNOTATE` — where every stage output is
canonicalized (RFC 8785 JSON → SHA-256) and folded into a hash-chained lineage. This is the
**same primitive the AEGIS governance runtime uses** (`src/core/canonicalize.ts`,
`src/frame/adaptive-lineage.ts`), applied to genomics instead of to agent state.

The terminal hash of the chain is a **reproducible, tamper-evident certificate** of the
entire computation. `test_replay_proof.py` asserts three invariants — all currently passing:

| # | Invariant | How it is proven | Result |
|---|-----------|------------------|--------|
| 1 | **Determinism** | 3 independent runs + a reversed-input run all yield one terminal hash | `f8cb0093b9b7447c…` (identical across separate processes) |
| 2 | **Tamper-evidence** | flip one base in one read → terminal hash changes; post-hoc forge a stored `VARIANT_CALL` output → `certify()` returns `is_valid: false` and localizes `broken_at="VARIANT_CALL"` | detected + localized |
| 3 | **Cross-stage lineage** | recompute a stage hash with a forged `previous_hash` → hash diverges, proving each stage binds the prior (a real chain, not independent digests) | bound |

Run it:

```bash
cd genomics
python3 test_replay_proof.py   # exit 0 = all three proven
python3 replay_pipeline.py     # prints the per-stage chain + terminal hash
```

Dependency-free (stdlib `hashlib`, `json`, `unicodedata`). No install step.

## Why it reproduces where standard pipelines don't

The determinism discipline is inherited directly from the AEGIS Rust/TS invariants:

- **No float in hashed state.** `canon()` *rejects* `float` — the allele-support decision is
  an integer count threshold (`CALL_MIN_ALT = 2`), never a floating allele-frequency cutoff.
  This is the genomics analogue of the runtime's "`f64` only via `to_bits()`" rule.
- **No dict/set iteration in hashed state.** Pileup columns are emitted as sorted
  `[base, count]` lists, never as a map — the same reason `ProjectionState` forbids
  `Set`/`Map` (iteration order is not guaranteed cross-implementation).
- **Deterministic tie-breaking.** Alignment sorts by `(pos, bases)`; variants sort by
  `(pos, ref, alt)`. Input order cannot change the output (invariant 1's reversed-input run).
- **No wall-clock, no RNG, no thread-order dependence.**

## Honest scope (what this is *not*)

- The aligner, pileup, and ClinVar table are **toy** — small enough to read in one sitting.
  The claim is about the **governance envelope**, not about calling accuracy on real reads.
- T2, not T1: promotion to T1 requires ≥3 independent validations against a real reference
  pipeline (e.g. wrapping a deterministic build of a production caller and proving the chain
  survives real BAM/VCF inputs). That is the next step, and it is a wrapping exercise — the
  envelope is stage-agnostic.
- Determinism ≠ correctness. A reproducible wrong answer is still wrong. What the certificate
  buys is that *the same input always yields the same output, and any post-hoc edit is
  provable* — the precondition for auditability, not a substitute for validation.

## Part 2 — the governed, cached, verifiable AI interpretation layer

The deterministic caller above proves the *envelope*. The point of AEGIS is that the
**AI layer plugs into the same envelope**. `interpret.py` + `interpret_demo.py` compose
three real runtime layers on top of the called variants:

1. **Governed inference** — the clinical interpretation is produced by a Claude call
   through the runtime's own client factory (`sovereign-omega-v2/python/anth_client.py`),
   default model `claude-opus-4-8` (`AEGIS_SWARM_MODEL`).
2. **Prompt caching** — the stable constitutional/clinical framing is sent as a
   `cache_control: ephemeral` block via the runtime's exact helper `make_cached_system`.
   Only the per-patient variant list is uncached.
3. **Verifiable lineage** — the interpretation is folded into the **same hash chain** as
   an `INTERPRET` stage whose payload binds the model id, the input-variant fingerprint,
   and the exact interpretation text.

**Live evidence** (real `claude-opus-4-8` call, two identical-prefix calls in one run):

```
[A] deterministic terminal hash : f8cb0093b9b7447cc44d7386…  (variants called: 1)
[C] call 1  cache_creation= 1605  cache_read=    0  in=53 out=499
    call 2  cache_creation=    0  cache_read= 1605  in=53 out=537
    prompt cache HIT — stable frame served at 10% cost
[B] interpretation folded into lineage; chain certifies: True  (model=claude-opus-4-8, live=True)
[D] edited stored interpretation → certify is_valid=False, broken_at=INTERPRET
```

Read it directly: the 1605-token constitutional frame is written to cache on call 1 and
served from cache on call 2 (`cache_read=1605`) at 10% input cost; only the 53-token
variant suffix pays full price each time. The two calls produce *different* output lengths
(499 vs 537 tokens) — generation is stochastic, which is the whole reason the chain
certifies **provenance, not reproducibility**.

Run it:

```bash
cd genomics
python3 interpret_demo.py            # offline, deterministic fixture — no credits spent
AEGIS_LIVE=1 python3 interpret_demo.py   # live governed + cached call (needs ANTHROPIC_API_KEY)
```

**The non-equivalence this makes concrete (and why it is the thesis):** the `INTERPRET`
record does *not* claim the model will reproduce this text — LLM output is stochastic.
What it proves is **integrity and provenance**: *this exact interpretation was produced
for this exact variant set by this exact model, and nothing was edited afterward* (step
D: a one-word edit to the stored interpretation flips `certify()` to invalid and localizes
`broken_at="INTERPRET"`). Determinism lives in the governance envelope, not in the model.
That is precisely the line between "the AI made it up and we can't tell" and "the AI's
output is auditable evidence." (`replayability ≠ correctness`; `governance ≠ alignment`.)

## The general pattern

Nothing here is genomics-specific except the stage functions. The chain accepts any
`(stage_name, output_dict)` sequence, so the identical envelope certifies any pipeline whose
intermediate state can be canonicalized — materials screening, financial model runs,
compliance evidence. Genomics is the worked example because clinical reproducibility is where
"the AI made it up" is least tolerable.
