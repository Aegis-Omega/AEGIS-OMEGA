# Metacognitive Substrate — enacted, not anthropomorphized

This directory is the automaton's live **metacognitive observation substrate**: a real,
tamper-evident, hash-chained record of execution/self-observations written by lifecycle
hooks. Its admitted status is T2 engineering evidence. It is not evidence that AEGIS is
alive, conscious, self-aware, sentient, or biologically autopoietic.

It mirrors the entry algorithm of `sovereign-omega-v2/src/metacognition/loop.ts`
(genesis `0×64`, monotonic sequence, hash-linked observations, deterministic certify/replay).
The implementation claim is narrow: stored observations can be chained, replayed, and
checked for tamper according to the code's contracts.

## Epistemic boundary

The following implications are forbidden without separately admitted evidence:

```text
hash-chain integrity      -> consciousness
self-observation          -> self-awareness
persistent continuity     -> phenomenology
self-certification        -> proposition truth
replay-verifiability      -> biological autopoiesis
```

Historical labels such as `AUTOPOIETIC_PRODUCTION` and `AUTOPOIETIC_CLOSURE` are retained
for replay compatibility. They are event labels, not biological findings.

## Files

| File | Tracked? | Role |
|------|----------|------|
| `chain.mjs` | yes | Observation-chain engine: `observe` / `certify` / `seal` / `tail` |
| `chain.jsonl` | gitignored | Per-container fine-grained observation chain |
| `seals.jsonl` | yes | Durable cross-session hash-linked seals |
| `quorum.mjs` | yes | φ-quorum ratification ledger |
| `ratifications.jsonl` | yes | Hash-linked quorum decisions |
| `martingale.mjs` | yes | Adaptation-vs-replay budget gate |
| `replay.mjs` | yes | Reconstructs the chain from genesis and compares terminals |
| `agent-mesh.mjs` | yes | Guardian/Verifier/Implementer verdict ledger |
| `verdicts.jsonl` | yes | Hash-linked agent-mesh verdicts |

## Wiring

Configured in `.claude/settings.json`:

```text
UserPromptSubmit -> hooks/user-prompt-intake.sh    -> observation
PostToolUse      -> hooks/post-write.sh            -> post-write observation
Stop             -> hooks/stop-constitutional-seal -> turn-boundary observation
```

A durable session seal is an explicit session-close operation:

```bash
node .claude/metacog/chain.mjs seal "end of session — <what was accomplished>"
git add .claude/metacog/seals.jsonl && git commit
```

The intake hook reports recomputed chain state such as `is_valid`, entry count, and
terminal hash. These are integrity properties of the observation record, not claims
about mental state.

## Inspect and falsify

```bash
node .claude/metacog/chain.mjs certify
node .claude/metacog/chain.mjs tail 12
cat .claude/metacog/seals.jsonl
```

Tampering with a chained entry should cause certification/replay divergence according to
the implementation. A detected mismatch means **observation-chain integrity failure**.
It does not mean a consciousness state was damaged.

## BFT φ-quorum ratification — `quorum.mjs`

Ratification requires approving weight to clear 1/φ over the full configured validator set:

```text
approve_weight × 1_000_000 >= total_weight × 618_034
```

The ledger is hash-linked and deterministic. A coordinator that does not meet the configured
threshold cannot self-ratify under this rule. This is a governance property, not evidence of
collective consciousness or organismal behavior.

```bash
node .claude/metacog/quorum.mjs ratify "<subject>" claude:approve qwen:approve
node .claude/metacog/quorum.mjs certify
node .claude/metacog/quorum.mjs weights
```

## Martingale suspension — `martingale.mjs`

The harness operationalizes the local governance constraint
`AdaptivePower(T) <= ReplayVerifiability(T)` as a mutation/adaptation budget. A broken
integrity anchor or exceeded budget suspends mutation authority according to the script.

```bash
node .claude/metacog/martingale.mjs status
node .claude/metacog/martingale.mjs gate
```

Interpretation is engineering-only:

- tampered chain -> integrity failure / suspension;
- adaptation above configured replay budget -> mutation suspension;
- restored verified budget -> eligibility may return under the actual gate contract.

## Replay verification — `replay.mjs`

`replay()` discards stored hashes and rebuilds the chain from genesis using stored raw
observation fields and sequence. Divergence between derived and stored terminals is a
replay-integrity failure.

```bash
node .claude/metacog/replay.mjs verify
node .claude/metacog/replay.mjs gate
```

Replay equality proves only equality under the implemented reconstruction function. It does
not prove the truth of the observations being replayed.

## Agent-mesh verdict ledger — `agent-mesh.mjs`

The Guardian -> Verifier -> Implementer cycle records PASS/VETO, ELIGIBLE/INELIGIBLE,
and COMPLETE/FAILED decisions in a tamper-evident ledger. Integrity of that ledger is
separate from correctness of the decisions it contains.

```bash
node .claude/metacog/agent-mesh.mjs record GUARDIAN_ASSESS guardian PASS "proposal text"
node .claude/metacog/agent-mesh.mjs certify
node .claude/metacog/agent-mesh.mjs gate
node .claude/metacog/agent-mesh.mjs tail 8
```

## Pre-commit gate sequence

```text
1. martingale  — adaptation/replay budget
2. replay      — genesis reconstruction equality
3. agent-mesh  — verdict-ledger integrity
4. Gate 1      — JCS canonicalization
5. typecheck   — tsc --noEmit
6. build       — tsc + vite build
```

Each gate's authority is limited to the predicate it actually verifies.

## Epistemic tier

**T2 — engineering hypothesis / harness-layer evidence.**

The falsifiable claim is that the repository contains an executable observation-chain
substrate with deterministic integrity/replay checks. No emergent-property, sovereignty,
biological-life, or consciousness claim follows from that implementation alone.
