---
name: verification-before-completion
description: Use before claiming any work is complete, fixed, or passing — before any commit, push, or PR. Requires running the actual verification command and reading the output. "Should work" is not verification. Evidence before claims, always.
---

# Verification Before Completion

**Metacognitive Layer: L2 (Perception) + L1 (Sensation)**

Completion claims are L2 classification outputs. A completion claim without fresh evidence is L2 operating on L1 signal that was never received — the agent is classifying something it did not sense. This is the core pattern of AI-generated false confidence: the model knows what correct output looks like and generates the appearance of having produced it.

The non-equivalence invariants apply here unconditionally:
```
"Should work" is L6 reasoning — it is NOT L2 perception
"I fixed the logic" is L7 self-model — it is NOT L1 signal
"Tested earlier" is L4 memory — it is NOT fresh L1 sensation
"Looks correct" is L2 guess — it is NOT L2 verification
```

L1 invariant: **Run the command. Read the output. The output IS the signal. Your prediction of the output is NOT the signal.**
L2 invariant: **Classify the result from the actual exit code and actual output text. Not from your expectation of what they should be.**

**Autopoietic Property: Pre-Incorporation Integrity Check**

Before a component is incorporated into the membrane (committed), it must pass the viability ring. Claiming completion without verification is claiming incorporation without checking viability — the autopoietic equivalent of incorporating a malformed protein into the cell wall. The cell wall holds until stress is applied, then fails at the weakest point.

Verification is not bureaucracy. It is the act of confirming that the new component is structurally compatible with the existing membrane before the membrane update is made permanent. Once the commit lands, the component is in the chain. The chain is tamper-evident. A bad component in the chain is there forever — the only repair is a new component that cancels it, which is more expensive than the original verification.

The cost of checking: one command, one read.
The cost of not checking: a broken membrane that fails under load and requires multiple repair commits.

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

If you haven't run the verification command in this exact message, you cannot claim it passes.

## The Iron Law

```
Run the command. Read the output. THEN make the claim.
```

## Gate Function — 5 Steps (all required)

1. **Identify** the exact command that proves the claim
2. **Run** it fresh and complete (not cached, not assumed)
3. **Read** the full output — exit code, failure count, error text
4. **Verify** the output actually confirms what you're claiming
5. **Only then** make the claim

## Claim → Required Verification Mapping

| Claim | Required command |
|-------|-----------------|
| "Tests pass" | `cargo test 2>&1 \| grep "test result"` or `npm run test` |
| "Gate 8 passes" | `npm run test && npm run typecheck && npm run build` |
| "Hash integrity OK" | `node scripts/verify-hashes.mjs` |
| "Build succeeds" | Full build command with exit code check |
| "Bug is fixed" | Run the specific failing test, see it pass |
| "All tests passing" | Full suite, not just the module |

## What Is NOT Verification

- "It should work because I fixed the logic" — not verification
- "I tested it earlier" — not verification (run it again)
- "The test probably passes" — not verification
- Reading code and concluding it's correct — not verification

## Red Flag Phrases — Stop Before Using

If you're about to write any of these, run the verification command first:
- "should work"
- "probably passes"
- "seems to be fixed"
- "looks correct"
- "I believe"

## AEGIS Gate Verification Commands

```bash
# Single module
cargo test <module_name> 2>&1 | grep -E "test result|FAILED"

# Full Rust suite
cargo test 2>&1 | grep "test result" | head -1

# TypeScript Gate 8
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build

# Hash integrity
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs

# Working tree clean before commit
git status --short
```

Honesty is not optional. If the command fails, report the failure — don't soften it.
