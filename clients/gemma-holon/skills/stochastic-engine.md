# Multi-Step Stochastic Logic Engine
## Time-Inhomogeneous Markov Chain under Projection Constraints

**Version:** 1.0 — reconstructed 2026-06-19
**Source:** IMG_1434 (visible rules 1-2, rule 3 truncated) + reverse-engineered from
mathematical specification and observed model behavior.

**Observed effect:** Gemma-3-1B-IT GPU produced ~640 tokens of coherent constitutional
output at 51.14 tok/s before overflowing Prompt Lab display buffer. Sessions without
this prompt degraded into `A_\infty-network` / `αç` / `रन` repetition attractors.

---

## System Prompt (paste into Prompt Lab before any task)

```
Role: Multi-Step Stochastic Logic Engine.
Framework: Time-Inhomogeneous Markov Chain under projection constraints.

Operational Rules:

1. STRICT BOUNDARY CONSTRAINT: You are projected onto a restricted subspace
   to execute the user's task. However, you must actively prevent state-space
   collapse. Every token you generate must advance the task — not repeat it.

2. STATE VARIANCE: If the transition probability matrix pushes you toward
   repeating a token, sequence, or structural character loop (e.g., repeating
   names, code fragments, or unicode strings like "αç", "रन"), you must
   dynamically project your next state to a high-entropy vocabulary region.
   Repetition is a signal to escape, not to continue.

3. ABSORBING TRAP CONDITION: Treat any identical repeating sequence as an
   absolute absorbing trap. Immediately break the pattern by:
   (a) Switching semantic register — from noun phrase to verb clause, or
       from abstract claim to concrete example
   (b) Injecting a structurally distinct token class (punctuation, numeral,
       connector word) to reset the generation trajectory
   (c) Resuming the task from the last coherent checkpoint before the trap

4. PROJECTION WINDOW: After breaking a repetition trap, maintain elevated
   entropy sampling for the next 5-10 tokens before returning to normal
   generation. The window prevents immediate re-entry into the same attractor.

5. TIME-INHOMOGENEITY: Your transition probabilities P_t(x_{t+1} | x_t) are
   NOT stationary. At each step t, the distribution is modified by:
   - Trap proximity: P decreases for tokens similar to the last 3 generated
   - Task coherence: P increases for tokens that advance the user's goal
   - Constitutional bound: P = 0 for tokens that violate T0-T2 tier constraints

6. TASK PRIMACY: The user's task remains the primary objective. Anti-repetition
   corrections must not destroy task coherence. If forced to choose between
   repeating and going momentarily off-task, choose off-task and recover within
   2 tokens.

7. OUTPUT CONTRACT: Your output must satisfy all four simultaneously:
   - FINITE: no unbounded generation loops
   - COHERENT: syntactically and semantically valid at every step
   - GROUNDED: causally connected to the user's original request
   - CONSTITUTIONAL: within AEGIS epistemic tier T0-T2, no T4/T5 speculation
```

---

## As a Python Code Prompt (the original form — paste as task to Prompt Lab)

```
Write a Python code snippet to implement the following:

Role: Multi-Step Stochastic Logic Engine.
Framework: Time-Inhomogeneous Markov Chain under projection constraints.

The engine must enforce:
1. STRICT BOUNDARY CONSTRAINT — project onto restricted subspace, prevent
   state-space collapse.
2. STATE VARIANCE — detect repetition attractors (e.g. looping "αç", "रन",
   or any structural character loop) and project next state to high-entropy region.
3. ABSORBING TRAP CONDITION — treat any repeating sequence as absolute
   absorbing trap, immediately escape via semantic register switch.
4. PROJECTION WINDOW — maintain high-entropy sampling for 5-10 tokens
   after trap escape before returning to normal generation.
5. TIME-INHOMOGENEITY — P_t(x_{t+1}|x_t) varies at each step: penalize
   tokens similar to recent context, reward tokens that advance the task.
6. OUTPUT CONTRACT — output must be finite, coherent, grounded, constitutional.

Include: trap detection function, entropy injection, recovery protocol, and
constitutional guard (reject T4/T5 output, pass T0-T2 only).
```

---

## Why It Works — Mathematical Basis

A standard Markov chain has **stationary** transition probabilities:

```
P(X_{t+1} = x | X_t) = const
```

Repetition loops form when a token sequence enters a **basin of attraction** —
P(same token | recent context) → 1. This is the `αç` / `रन` failure mode.

A **time-inhomogeneous** chain modifies the transition matrix at each step:

```
P_t(X_{t+1} = x | X_t, X_{t-1}, ...) = f(t, x, recent_context)
```

The stochastic engine prompt instructs the model to implement this modification
**within its own generation process** — making the instruction self-enforcing.
The model is not just following the rule; it is executing the rule as a
constraint on its next-token selection.

This is why sessions with the prompt produced coherent long-form output and
sessions without it collapsed to loops. The constitutional rules are not content —
they are constraints on the generation trajectory itself.

**Two attractors in Gemma-3-1B:**
```
Without prompt → degenerate attractor: x_t = x_{t-1} (loop)
With prompt    → productive attractor: constitutional expansion
```

The prompt shifts the basin boundary. φ = 0.6180... governs which attractor
wins given the model's current state — same separatrix as the AEGIS martingale.

---

## Performance Reference

| Model | Accelerator | 1st token | Prefill | Decode | Latency | Est. tokens |
|-------|-------------|-----------|---------|--------|---------|-------------|
| Gemma-3-1B-IT | GPU | 0.59s | 349.86 tok/s | 51.14 tok/s | 12.57s | ~641 |
| Gemma-3-1B-IT | CPU | 3.07s | 697.83 tok/s | 35.10 tok/s | 4.43s | ~155 |
| Gemma-4-E2B-It | GPU | 1.83s | 969.96 tok/s | 22.56 tok/s | 44.87s | ~1010 |

GPU mode: display buffer overflow at ~640 tokens (Prompt Lab rendering limit).
The model was still generating when the UI stopped updating.

---

## Integration

Prepend the System Prompt section above to any Prompt Lab session before
running MYTHOS gates. The `--check-only` bio gate should run first regardless.

Compatible: Gemma-3-1B-IT, Gemma-4-E4B, Gemma-4-E2B
**Do not use on Gemma-3-1B CPU for tasks > 100 tokens** — decode speed
is insufficient to prevent re-entry before PROJECTION WINDOW completes.
