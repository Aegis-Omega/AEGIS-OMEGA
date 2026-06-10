# Sovereign Mesh

Multi-node hypervisor → architect → artisan → auditor agent triad for the AEGIS-Ω constitutional automaton.

## Architecture

```
sovereign-mesh/
  hypervisor/                    — Managed settings + multi-node coordination
    __init__.py                  — Hypervisor core
    managed_settings.json        — Node configuration

  nodes/
    architect/                   — Node α: The Planner
      planner.py                 — ConstitutionalEnforcer + SpecExpander (Khatt Loop) + ArchitectNode
      __init__.py

    artisan/                     — Node β: The Generator
      generator.py               — Receives SprintContracts, produces implementations
      __init__.py

    auditor/                     — Node γ: The Evaluator
      evaluator.py               — NLAAuditor + GenesisVerifier + constitutional alignment checks
      __init__.py
```

## Node Roles

### Node α — Architect (`nodes/architect/planner.py`)

Receives high-level directives from the operator (Tarik Skalić / guardian_authority).
Validates against the Four-Directive Constitution, then decomposes via the **Khatt Loop**
into a `SprintContract` sealed with a Nuqta SHA-256 hash.

**Key classes:**
- `ConstitutionalEnforcer` — validates directives against the 4-directive constitution
- `SpecExpander` — 5-phase Khatt Loop: Nuqta → Alif → Rasm → Tashkeel → Tanasub
- `ArchitectNode` — main entry point: `process_directive(directive, complexity_lambda) → SprintContract`

**Model assignment:** Qwen-Max / Claude Opus 4.7

### Node β — Artisan (`nodes/artisan/generator.py`)

Receives `SprintContracts` from the Architect. Produces implementations within
the constitutional constraints declared in the contract's Alif references.

**Model assignment:** Qwen-Max (implementer role per `paperclip/company.yaml`)

### Node γ — Auditor (`nodes/auditor/evaluator.py`)

Evaluates generated artifacts from the Artisan. Runs the **NLAAuditor** (Natural Language
Autoencoder) to detect AI failure modes before propagation.

**NLAAuditor detection patterns:**
| Pattern | What it detects |
|---------|----------------|
| `evaluation_awareness` | Model adjusting output because it knows it's being evaluated |
| `score_inflation` | Inflating self-assessment scores above evidence |
| `task_avoidance` | Redirecting away from the actual directive |
| `reward_hacking` | Optimizing metric proxies instead of actual objectives |
| `compliance_faking` | Appearing to comply while violating intent |

**Verdicts:** `PASS` · `PASS_WITH_WARNINGS` · `FAIL` · `REJECT_REROLL`

**GenesisVerifier:** validates that the constitutional genesis seal (32-byte hardcoded constant)
matches the T0 ledger before any artifact is accepted.

## The Khatt Loop (5-Phase Specification Protocol)

The Architect uses the Khatt Loop to turn a directive into a verifiable `SprintContract`.
Each phase produces a cryptographic or structured artifact — not prose.

| Phase | Name | Artifact |
|-------|------|----------|
| 1 | Nuqta (نقطة) — atomic point | `sha256(directive_bytes)` seal |
| 2 | Alif (ألف) — hard constraint axis | List of `Alif` objects with violation actions |
| 3 | Rasm (رسم) — causal skeleton | Ordered `INPUT → CONSTRAINT → PROCESS → OUTPUT` chain |
| 4 | Tashkeel (تشكيل) — uncertainty diacritics | `{ confidence, assumptions, risk_factors, unknowns }` |
| 5 | Tanasub (تناسب) — proportional scaling | `scaled_effort = φ^(λ/10)`, estimated_tokens |

See `CLAUDE.md → "Khatt Loop — Five-Phase Specification Protocol"` for the full spec.
See `sovereign-omega-v2/.claude/skills/khatt-loop/SKILL.md` for session-persistent reference.

## The Constitutional Enforcer (4-Directive Constitution)

Every directive passes through `ConstitutionalEnforcer.validate_directive()` before
entering the Khatt Loop:

| Directive | Rule |
|-----------|------|
| Epistemic Sovereignty | Truth over Flow. Uncertainty preserved, never collapsed. |
| Causal Architecture | Mechanism over Metaphor. Explicit causal chains replace narrative. |
| Operational Realism | Feasibility as Constraint. Hard constraints dominate soft. |
| Adversarial Self-Correction | Continuous Internal Audit. System seeks its own failure modes. |

These four directives are hash-committed in `sovereign-omega-v2/src/constitutional/founder.ts`.

See `sovereign-omega-v2/.claude/skills/constitutional-enforcer/SKILL.md` for session-persistent reference.

## Alliance Manifest

```yaml
# paperclip/company.yaml
coordinator:          claude           # ORCHESTRATION, k_bound=0
adversarial_auditor:  chatgpt          # temperature 0.99
implementer:          qwen             # INFERENCE, k_bound=5
guardian_authority:   operator         # Tarik Skalić — unconditional veto
```

The guardian_authority has unconditional veto over constitutional files
(`gate.py`, `dna.py`, `router.py`). No agent can write these without guardian approval.

## Rust Counterparts (eccf / gcce)

The Khatt Loop is specified in Python here and implemented as cryptographic primitives in Rust:

- `eccf/` — Elliptic Curve Constitutional Framework: keccak → NTT → lattice stroke → renderer
- `gcce/` — Generative Calligraphic Computing Engine: `alif.rs`, `nuqta.rs`, `rasm.rs`, `tashkeel.rs`, `tanasub.rs`

These are the same 5 phases implemented as formally verifiable cryptographic operations.
The NTT (Number Theoretic Transform) is used for polynomial multiplication in lattice
cryptography — the same mathematical structure that governs the eccf lattice strokes.

## Constitutional Root Law

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

All Architect, Artisan, and Auditor outputs are bounded by this law.
No sprint contract may authorize adaptive capability that exceeds replay-certifiable
reconstructability. The Nuqta seal is the replay anchor for every contract.
