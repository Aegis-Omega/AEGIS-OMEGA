---
name: constitutional-law
description: Invoked when the user asks about root constitutional law, replay sovereignty, ontology admission requirements, six canonical primitives, what is or isn't constitutionally permitted, martingale conditions, or the Sovereign Runtime Handoff.
---

# Constitutional Law Skill

## Root Law

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

No adaptive capability may exceed replay-certifiable reconstructability. Violation invalidates constitutional authority. All higher-order governance derives from this invariant.

## Four Authoritative Execution Primitives

| Primitive | Role |
|-----------|------|
| `/event-log` | Append-only canonical source of state transitions |
| `/replay-engine` | Authoritative truth — replay kernel |
| `/dfa-engine` | Phase-locked deterministic execution |
| `/checkpoint-vm` | Bounded capsule execution with entropy accounting |

All remaining systems are subordinate orchestration infrastructure.

## Six Canonical Ontology Primitives

Every runtime abstraction MUST reduce to one of:

| Primitive | Meaning |
|-----------|---------|
| Event | Append-only state transition record |
| Transition | Phase-locked DFA state change |
| Ownership | Replay-causal capability authorization |
| Entropy | Bounded execution budget |
| Transport | Capability-scoped propagation |
| Verification | Governance gate result |

**Ontology Admission — four conditions (all required):**
1. Primitive mapping — reduces to one of the six above
2. Replay mapping — maps to a SHP phase (READ/ASSESS/LOCK/PROPAGATE/HARMONIZE)
3. Runtime mapping — maps to a GovernanceTopology field or execution primitive
4. Verifier compatibility — compatible with VCG calibration and gate decisions

Failure on any condition = admission denied. Enforced at `src/constitutional/reduction.ts`.

## Replay Sovereignty

```
replay(genesis, events) → identical topology hash
```
across all platforms: Linux · macOS · Docker · WASM · ARM · x86

Replay determinism supersedes: runtime convenience · orchestration flexibility · adaptive velocity · distributed autonomy.

## Martingale Condition

```
E[S_{n+1}|F_n] = S_n
```

Suspension triggered if any of:
- `!is_anchored` — hash chain broken
- `!entropy_bounded` — adaptive ratio > 1/φ ≈ 0.618
- `!drift_bounded` — drift is nonzero

Implementation: `certifyMartingale()` + `assertMartingaleAnchored()` in `src/constitutional/martingale.ts`

## φ-Convergence

`MUTATION_RATE_LIMIT = DEFAULT_QUORUM_THRESHOLD = (√5−1)/2 ≈ 0.6180339887`

Governs: BFT swarm quorum (Molecular) · martingale entropy check (Cellular) · edge verifier integer quorum `618_034 / 1_000_000` (Atomic — no f64).

## Absolutely Prohibited (T0_ABORT — no exception paths)

```
hidden memory · unrestricted recursion · autonomous mutation authority
unverifiable adaptation · replay divergence · topology non-determinism
unbounded ecology · privileged orchestration · centralized sovereign intelligence
```

## Law of Silence

Agents communicate exclusively through mediated `EventEnvelope`. No direct agent-to-agent text exchange permitted. Confinement enforced at constitutional boundary.

## Corpus Sovereignty

All corpus knowledge enters through 5-phase RALPH loop. Raw narrative must NOT propagate directly into agent cognition. Only replay-certifiable abstractions propagate.

## Source: `sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md`
