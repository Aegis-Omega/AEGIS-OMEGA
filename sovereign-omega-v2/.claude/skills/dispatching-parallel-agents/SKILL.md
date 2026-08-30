---
name: dispatching-parallel-agents
description: Use when facing 2 or more independent tasks that can proceed without shared state or sequential dependencies. Dispatch one agent per independent problem domain. Do NOT use when failures are related or when agents would need to share state.
---

# Dispatching Parallel Agents

Delegate independent work to specialized agents with isolated context. Each agent gets exactly what it needs — no session history, no inherited context.

## When to Use

**Use when:**
- 3+ test files failing with different root causes
- Multiple independent gate modules need writing
- Multiple subsystems broken independently
- Each problem is understandable without context from others

**Do NOT use when:**
- Failures are related (fixing one might fix others)
- Agents would read/write the same files simultaneously
- Sequential dependency exists between tasks

## The Pattern

### Step 1 — Identify Independent Domains

Group work by what's broken or what needs building. Each domain must be completable without knowledge of the others.

Example for AEGIS gate building:
- Domain A: `gossip_broadcast_timeout.rs` — independent module
- Domain B: `gossip_broadcast_sequence.rs` — independent module
- Domain C: Update `lib.rs` registrations — depends on A and B completing first (NOT parallel)

### Step 2 — Write Focused Agent Prompts

Each agent prompt must be:
- **Focused**: one module/subsystem/problem
- **Self-contained**: include file paths, relevant constants, the pattern to follow
- **Specific**: state exact expected output

For AEGIS gate agents, include:
- The full gate module pattern (struct, hash formula, 19 tests)
- Which genesis constant name to use
- Which threshold constant and value
- The exact `lib.rs` comment block format

### Step 3 — Dispatch in Parallel

Send all agent calls in a single message (they run concurrently):

```
Agent A: write gossip_broadcast_timeout.rs
Agent B: write gossip_broadcast_sequence.rs
```

### Step 4 — Review and Integrate

After both complete:
1. Read each agent's output
2. Verify no conflicts between files
3. Run `cargo test <module_a> && cargo test <module_b>`
4. Register both in `lib.rs`
5. Run full suite

## Agent Prompt Template for AEGIS Gates

```
Write aegis-cl-psi/src/<module_name>.rs following the standard gate pattern:

Constants:
  pub const <NAME>_GENESIS_HASH: [u8; 32] = [0u8; 32];
  pub const <THRESHOLD>: u32 = <value>;

Entry fields: epoch_end(u64), <primary>(u32), <secondary>(u32),
  <rate>_pct(u32), <flag>(bool), entry_hash([u8;32]), prev_hash([u8;32])

Hash: SHA-256(prev[32]‖epoch_end_be8‖<primary>_be4‖<secondary>_be4‖<rate>_be4‖<flag>_byte)
Rate: (<primary>*100)/max(<secondary>,1) capped at 100
Flag: <rate>_pct <op> <THRESHOLD>
Aggregates: <flag>_count(), total_<primary>(), mean_<rate>_pct()
Tests: exactly 19 (record fields, threshold, aggregates, hash chain, verify_chain, determinism)

DO NOT modify lib.rs — only write the module file.
```

## Common Mistakes

- **Too broad scope**: "fix all failing tests" — agents need one specific domain
- **Missing context**: agents don't inherit your knowledge — include file paths and patterns
- **No constraints**: specify what they should NOT touch (e.g., "do not modify lib.rs")
- **Sequential disguised as parallel**: if agent B needs agent A's output, they are not parallel
