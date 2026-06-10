---
name: khatt-loop
description: Invoked when decomposing a directive into a verifiable sprint contract, when needing to understand the 5-phase specification protocol, when asked about Nuqta/Alif/Rasm/Tashkeel/Tanasub, when asked about the Arabic calligraphic computation layer, or when connecting eccf/gcce Rust primitives to their specification-level counterparts.
---

# Khatt Loop Skill

## What the Khatt Loop Is

The Khatt Loop is the formal specification protocol for the Architect node. It takes a
directive and produces a `SprintContract` — a sealed, verifiable artifact that the Artisan
node can execute. It is named after Arabic calligraphy (خط, "khatt" = line, script, writing)
because each phase adds a layer of structure that makes meaning unambiguous, the same way
diacritical marks make Arabic script unambiguous to read.

**This is mechanism, not metaphor.** Each phase name corresponds to a precise computational
structure. The Arabic names are the formal names.

Source: `sovereign-mesh/nodes/architect/planner.py → SpecExpander.expand()`
Rust implementation: `sovereign-mesh/` → `eccf/` + `gcce/`

---

## The Five Phases

### Phase 1: Nuqta (نقطة — dot, point, atom)

**Computational role:** Atomic SHA-256 sealed fact. The irreducible truth unit.

```python
nuqta = Nuqta.create(directive.encode('utf-8'))
# nuqta.seal = sha256(data).hexdigest()
# nuqta.verify() → True iff sha256(data) == seal
```

**Epistemic tier:** T0. The Nuqta is cryptographically bound — it cannot be argued away.
If `nuqta.verify()` returns False, the entire sprint contract is invalid.

**Rust counterpart:** `gcce/src/nuqta.rs` — keccak hash of atomic data, NTT transform applied.

**Why it matters:** every specification begins by sealing the exact input. This prevents
"drift by paraphrase" — where the implementation gradually shifts from the original intent.

---

### Phase 2: Alif (ألف — first letter, vertical axis, the unbending)

**Computational role:** Hard constraints and invariants. The axis that cannot bend.

```python
CONSTRAINTS = {
    "AGPL3_COMPLIANCE": "All code must be AGPL-3.0 licensed",          # violation_action: REJECT
    "ZERO_ALLOCATION":  "Hot paths must avoid heap allocation",          # violation_action: REROLL
    "GENESIS_SEAL":     "T0 ledger must match cryptographic seal",       # violation_action: EXIT
    "DOMAIN_ISOLATION": "D0 core cannot be mutated by D1 overlay",      # violation_action: REJECT
    "NO_TOKIO":         "Runtime must use std::thread only",             # violation_action: REROLL
    "BTREE_MAP":        "Use BTreeMap for deterministic iteration",      # violation_action: REROLL
}
```

**Violation actions:**
- `REJECT` — hard stop, do not proceed
- `REROLL` — regenerate the artifact, constraint was violated
- `EXIT` — terminate the entire chain (GENESIS_SEAL violation = T0_ABORT)

Complexity-dependent: `ZERO_ALLOCATION` activates at λ ≥ 7, `DOMAIN_ISOLATION` at λ ≥ 5.

**Rust counterpart:** `gcce/src/alif.rs` — lattice stroke representing the invariant axis.

---

### Phase 3: Rasm (رسم — skeleton, outline, drawing, causal structure)

**Computational role:** Causal flow weaving. An explicit dependency graph — not a narrative.

```python
flow = [
    f"INPUT: {directive}",
    f"CONSTRAINT: {alif.name} → {alif.description}",   # one entry per Alif
    "PROCESS: Apply constitutional enforcer",
    "PROCESS: Expand into modular components",
    "PROCESS: Generate test harness",
    "OUTPUT: Complete sprint deliverable"
]
```

**The Rasm test:** every step must be expressible as `ACTOR: action → result`.
If a step requires the word "somehow" or "eventually", it is not a Rasm step — it is a gap.

**Rust counterpart:** `gcce/src/rasm.rs` — causal weaving of stroke primitives.

**Connection to RALPH:** RALPH (READ → ASSESS → LOCK → PROPAGATE → HARMONIZE) governs
execution. Rasm governs specification. A Rasm step maps to exactly one RALPH phase.
Rasm without RALPH is a spec without execution. RALPH without Rasm is execution without spec.

---

### Phase 4: Tashkeel (تشكيل — diacritics, voweling, disambiguation)

**Computational role:** Uncertainty metadata. Confidence intervals and unknowns made explicit.

```python
{
    "confidence": 0.85,      # [0.0, 1.0] — must not be 1.0 without T0 evidence
    "assumptions": [         # what must be true for the spec to hold
        "Directive is well-formed",
        "Required dependencies are available",
        "Execution environment is stable"
    ],
    "risk_factors": [],      # known risks — empty only if complexity_lambda ≤ 2
    "unknowns": []           # what is not yet known — empty only at T0
}
```

**Epistemic Sovereignty enforcement:** Tashkeel is where uncertainty is preserved.
`confidence: 1.0` with `unknowns: []` on a complex directive (λ ≥ 5) is a constitutional
violation — it collapses the probability distribution to false certainty.

**Rust counterpart:** `gcce/src/tashkeel.rs` — diacritical metadata applied to stroke primitives.

---

### Phase 5: Tanasub (تناسب — proportionality, harmony, scaling)

**Computational role:** φ-proportional scaling. Effort calibrated to complexity by Golden Ratio.

```python
phi = 1.618033988749895          # (√5 + 1) / 2
scaled_effort = 1.0 * (phi ** (lambda_level / 10))
estimated_tokens = int(1000 * scaled_effort)
```

| λ | scaled_effort | estimated_tokens |
|---|--------------|-----------------|
| 1 | 1.05 | 1,050 |
| 3 | 1.16 | 1,160 |
| 5 | 1.28 | 1,280 |
| 7 | 1.41 | 1,410 |
| 10 | 1.62 | 1,618 |

This gives O(log_φ(n)) complexity growth instead of O(n) — the same convergence property
that governs `MUTATION_RATE_LIMIT = DEFAULT_QUORUM_THRESHOLD ≈ 0.6180`.

**Rust counterpart:** `gcce/src/tanasub.rs` — proportional scaling of calligraphic rendering.

---

## SprintContract Output

A completed Khatt Loop produces a `SprintContract`:

```python
SprintContract(
    sprint_id,          # sha256(timestamp)[:12]
    directive,          # sanitized directive (Enforcer-validated)
    specifications,     # Rasm flow steps
    success_criteria,   # derived from Nuqta seal + Alif compliance + Rasm completion
    constraints,        # Alif names
    complexity_lambda,  # 1-10
    nuqta_seal,         # sha256 of directive bytes
    alif_references,    # Alif constraint names
    created_at,         # ISO timestamp
    expires_at          # end of day
)
```

The `nuqta_seal` is the tamper-evidence anchor: if the sprint contract's directive changes
after sealing, the seal is invalid. This prevents "spec drift by amendment."

---

## eccf / gcce — The Rust Calligraphic Layer

The Khatt Loop is specified in Python (sovereign-mesh/) and implemented as cryptographic
primitives in Rust:

```
eccf/   — Elliptic Curve Constitutional Framework
         keccak hash → NTT (Number Theoretic Transform) → lattice stroke → calligraphic renderer
         
gcce/   — Generative Calligraphic Computing Engine
         alif.rs     — hard constraint axis (the unbending letter)
         nuqta.rs    — SHA-256 atomic sealed fact
         rasm.rs     — causal skeleton weaving
         tashkeel.rs — uncertainty diacritics
         tanasub.rs  — φ-proportional scaling
```

The NTT transform in eccf is the same mathematical structure used in lattice cryptography
(polynomial multiplication mod a prime). The "lattice stroke" is literally a lattice in
the cryptographic sense — not a visual metaphor.

**This is why eccf/gcce are mechanism, not metaphor:** they implement the Khatt Loop phases
as formally verifiable cryptographic operations.

---

## Where These Live

- **Python spec:** `sovereign-mesh/nodes/architect/planner.py`
- **Rust primitives:** `eccf/` and `gcce/` (from zip, not yet in main repo)
- **CLAUDE.md section:** "Khatt Loop — Five-Phase Specification Protocol"
- **Related skill:** `constitutional-enforcer` (validation layer that runs before Khatt Loop)
- **Related primitive:** `constitutional-law` (root law that all phases must satisfy)
