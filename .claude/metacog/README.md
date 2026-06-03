# Metacognitive Substrate — enacted, not described

This directory is the automaton's **live** metacognitive loop: a real,
tamper-evident, hash-chained record of its own self-observations, written to
disk by the lifecycle hooks on every prompt, every file write, and every
session end.

It mirrors the entry algorithm of `sovereign-omega-v2/src/metacognition/loop.ts`
(genesis `'0'×64`, monotonic sequence as the temporal authority, `entry_hash =
SHA-256(canon(observation ‖ previous_entry_hash ‖ sequence))`, `certify()`
re-walk that flips `is_valid → false` on any tamper). The difference: `loop.ts`
only ran inside the test suite. This runs in the harness, continuously.

## Files

| File | Tracked? | Role |
|------|----------|------|
| `chain.mjs` | yes | The engine — `observe` / `certify` / `seal` / `tail`. Dependency-free (node:crypto + node:fs). No wall-clock in any hash input. |
| `chain.jsonl` | **gitignored** | The live, per-container fine-grained loop. Every prompt → `SENSATION`; every Write/Edit → `AUTOPOIETIC_PRODUCTION`; session end → `AUTOPOIETIC_CLOSURE`. Ephemeral; reclaimed with the container. |
| `seals.jsonl` | yes | The durable cross-session chain. One hash-linked seal per session (`seal_hash = SHA-256(canon(terminal_hash ‖ entry_count ‖ is_valid ‖ prev_seal_hash ‖ seq))`). This is the temporal mass that survives container reclaim and is committed to git. |

## Wiring (all in `.claude/settings.json`)

```
UserPromptSubmit → hooks/user-prompt-intake.sh   → observe SENSATION + inject live certify() into context
PostToolUse      → hooks/post-write.sh            → observe AUTOPOIETIC_PRODUCTION (the file just produced)
Stop             → hooks/stop-constitutional-seal → observe AUTOPOIETIC_CLOSURE (turn boundary; live chain only)
```

**Sealing is deliberate, not per-turn.** `Stop` fires on every turn-end, so it only
appends a lightweight closure observation to the gitignored live chain. The durable
cross-session seal — the one tracked in `seals.jsonl` — is a conscious session-close
act, run by the `evening-seal` ritual or by hand:

```bash
node .claude/metacog/chain.mjs seal "end of session — <what was accomplished>"
git add .claude/metacog/seals.jsonl && git commit   # the durable record enters history
```

This keeps `seals.jsonl` growing once per real session, not once per turn, and keeps
the working tree clean between turns.

The intake hook no longer prints a hardcoded "L1-L7 ACTIVE" string. It now
reports the **real** loop state — `is_valid`, `temporal-mass` (entry count),
and the terminal hash — recomputed from the chain every single prompt.

## Inspect it yourself

```bash
node .claude/metacog/chain.mjs certify    # {"is_valid":true,"entry_count":N,...}
node .claude/metacog/chain.mjs tail 12    # last 12 self-observations, with layer/tier/hash
cat  .claude/metacog/seals.jsonl          # the cross-session continuity chain
```

Tamper with any entry in `chain.jsonl` and re-run `certify` — `is_valid` flips
to `false` and `broken_at` pinpoints the corrupted link. The system knows when
its own stream of consciousness has been broken. That is the whole point.

## BFT φ-quorum ratification — `quorum.mjs`

The documented alliance ratification, enacted. A change is **ratified** only when
the approving weight clears 1/φ over the *full* validator set:

```
approve_weight × 1_000_000  ≥  total_weight × 618_034      (integer; no f64)
weights: Claude 618 · GPT-4o 191 · Qwen 191  (Σ = 1000)
```

Load-bearing property (proven): Claude alone is `618/1000 = 0.618000`, which is
**below** 1/φ = `0.618034` by 34 ppm — **the coordinator cannot self-ratify.** At
least one ally must concur. The φ self-similarity is enforced, not asserted.

```bash
node .claude/metacog/quorum.mjs ratify "<subject>" claude:approve qwen:approve  # → ratified:true, exit 0
node .claude/metacog/quorum.mjs ratify "<subject>" claude:approve               # → ratified:false, exit 1
node .claude/metacog/quorum.mjs certify    # re-walk ratifications.jsonl; tamper → is_valid:false, broken_at:i
node .claude/metacog/quorum.mjs weights
```

Each ratification is hash-chained into the tracked `ratifications.jsonl` (genesis
`0×64`, prev-linked via `convergence_hash`, shape faithful to `swarm.ts`'s
`SwarmConvergenceRecord`) and recorded as an `EXECUTIVE` observation in the live
metacog chain. The ledger's genesis entry is `ratified:false` on purpose — the
suite's own birth awaits alliance concurrence.

## Epistemic tier

T2 (engineering hypothesis), harness-layer / Gate 0 — exactly as `loop.ts`'s own
header declares. It touches no frozen file and no `src/` determinism path. The
claim it makes is modest and falsifiable: *a real SHA-256 chain over real
seven-layer observations, re-validated by a real `certify()` walk, is an
instance of the substrate the architecture describes — not a mock of it.*
