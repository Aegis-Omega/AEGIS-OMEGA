---
name: execution-boundary
description: Invoked when the user asks about execution budget constraints, combinatorial proof limits, cost ceiling enforcement, k·C_eval ≤ B_max, bounded agent execution, or how to prevent runaway inference cost in AEGIS. Source: From Intent to Execution, tier T2.
---

# Execution Boundary Equation — k·C_eval ≤ B_max

**Epistemic Tier: T2** — engineering hypothesis. The equation is analytically sound; the specific coefficient values for AEGIS governance workloads are empirical unknowns pending measurement.

**Corpus Lineage:** `corpus_lineage_hash: pending-drive-access` · Source: From Intent to Execution (ARBITRATION: admitted T2; "goal mis-specification / autopoietic framing" quarantined)

---

## Constitutional Claim

The execution boundary equation `k · C_eval ≤ B_max` provides a hard pre-flight bound on agent execution cost: `k` is the number of evaluation steps (tool calls, inference calls, loop iterations), `C_eval` is the estimated cost per step, and `B_max` is the declared budget ceiling — enabling the AEGIS agent executor to reject an execution plan before it starts if the projected cost exceeds the constitutional limit.

---

## Key Invariants

- **Pre-flight, not post-hoc** — the constraint is evaluated against the *planned* execution path before any inference call is made; a plan that violates the bound is rejected at ASSESS phase, not discovered after the budget is exhausted
- **`k` is replay-reconstructable** — the step count `k` must be deterministically derivable from the task specification, not from wall-clock observation; it is bounded by the declared `maxTurns` in the agent constitution (RULE-07 entropy budget)
- **`C_eval` is conservative** — use the worst-case cost per step (e.g., max `output_tokens × price/token` for the configured model), not the average; underestimating `C_eval` is a constitutional violation
- **`B_max` is per-session, not global** — each agent session declares its own `B_max` in the `AgentSession` spec; sessions share no budget; a runaway session cannot exhaust a budget that was never allocated to it
- **Relation to martingale** — `B_max` is the financial analog of `ReplayVerifiability(T)`; the inequality `k · C_eval ≤ B_max` mirrors `AdaptivePower(T) ≤ ReplayVerifiability(T)` — both are bounding laws that prevent unbounded growth

---

## AEGIS Integration Points

| Component | Where the bound is enforced |
|-----------|----------------------------|
| `src/agents/executor/loop.ts` | RALPH ASSESS phase: compute `k_planned · C_eval_per_step` before first LOCK; reject if > `B_max` |
| `src/api/managed-agent-client.ts` | `startSession()` accepts `budget_ceiling_usd: number`; passes as `B_max` to the executor |
| `src/agents/constitution/agent-constitution.ts` | RULE-07 `entropy_budget_fixed` is the Q16.16 representation of `B_max` |
| `packages/shared/lib/constitutional-ai.ts` | `callConstitutional()` accepts `max_cost_usd` option; enforces bound before each call |

---

## Equation Derivation

```
Given:
  k        — number of evaluation steps (tool calls + inference calls)
  C_eval   — worst-case cost per step (USD)
  B_max    — declared budget ceiling (USD)

Constraint:
  k · C_eval ≤ B_max

Solved for k (max allowable steps):
  k_max = floor(B_max / C_eval)

Example (claude-sonnet-4-6, 1K output tokens/step @ $0.015/1K tokens):
  C_eval = 0.015
  B_max  = 0.50  (50 cents per session)
  k_max  = floor(0.50 / 0.015) = 33 steps
```

If `k_planned > k_max`, the RALPH ASSESS phase returns `PLAN_REJECTED: execution_boundary_exceeded` and the LOCK phase does not fire.

---

## Tier Promotion Criteria (T2 → T1)

1. Implement `assertExecutionBoundary(k, c_eval, b_max)` in `src/agents/executor/loop.ts`
2. Add test: plans that violate the bound throw `ExecutionBoundaryError` before any tool call fires
3. Empirically calibrate `C_eval` for each configured model from 10+ production sessions; publish coefficients in `src/agents/executor/cost-coefficients.ts`

---

## Source

Admitted T2 engineering claim from corpus ARBITRATION (From Intent to Execution). Directly relates to RULE-07 (entropy budget) in the Agent Constitution and to the `task_budget` feature of the Claude API (`output_config.task_budget`).
