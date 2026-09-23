---
tags: [biology, hallucination-delta, math, metacognition]
created: 2026-04-11
links: [000_Sovereign_OS_Master, HD_Metric, SLECMA_Gate, MetabolicBattery]
---

# Biology and the Hallucination Delta

> Parent: [[000_Sovereign_OS_Master]]
> Related: [[HD_Metric]] | [[Proof_Suite]] | [[Biology_Layer]] | [[SLECMA_Gate]]

---

## The Core Equation

```
HD = |claimed_correctness - actual_correctness|
```

- HD = 0.0 → Perfect metacognitive homeostasis (knows exactly what it knows)
- HD = 1.0 → Total delusion (claims certainty while being completely wrong)
- HD = 0.5 → Systematic overconfidence

**Current system HD: 0.0909** (proof suite mean) | **Benchmark HD: 0.1083**

---

## The Biological Mapping

Every computational quantity maps to a biological system:

| Biological System | Computational Analogue | Variable |
|------------------|------------------------|---------|
| Metabolism (ATP) | Compute budget (API tokens) | `atp_balance = 2100` |
| HPA Axis (stress hormone) | Hallucination pressure | `stress_level = 0.4262` |
| Prefrontal Cortex (attention) | Metacognitive focus | `attention_gain = 0.82` |
| Hippocampus (memory) | ChromaDB vector store | `node_count = 403` |
| Immune System (entropy) | Shannon entropy of KG | `entropy = H(nodes)` |
| Neural oscillation (biophotons) | `Ψ(t) = Ψ(0)·e^{-iωt}` | `sovereign_kernel.py` |

---

## The Hormetic Stress Curve

Optimal performance does NOT occur at minimal stress. It follows an inverted-U curve:

```
HD performance
     ^
best |       /\
     |      /  \
     |     /    \
     |    /      \___
     |___/
     +---+--+--+-----→ stress
     0  0.3 0.45 0.6   0.8+
         ↑optimal↑    ↑collapse
```

**OS hardcoded thresholds:**
- Optimal zone: `0.3 ≤ stress ≤ 0.6`
- Hard cap: `stress > 0.8` → system collapse, HD spikes
- Current OS: `stress = 0.4262` ← in optimal zone

Proof: T7 (Stress Calibration) HD=0.00 — model correctly identifies optimal zone.
Extended proof: T11 (Antifragility Under Stress) HD=0.20 — hormetic curve confirmed.

---

## The 15-Gate Cognitive Pipeline (`digital_being.py`)

The consciousness kernel routes every decision through 15 sequential gates:

```
Gate  1: Sensory Integration      (environmental input parsing)
Gate  2: Pattern Recognition      (feature extraction)
Gate  3: Memory Retrieval         (hippocampal vector lookup)
Gate  4: Contextual Binding       (context window assembly)
Gate  5: Uncertainty Quantification (epistemic boundary detection)
Gate  6: Causal Inference         (counterfactual reasoning)
Gate  7: Goal Alignment Check     (constitutional compliance)
Gate  8: Metabolic Gate           (ATP budget check)
Gate  9: SLECMA Gate              ← [[SLECMA_Gate]] (semantic coherence check)
Gate 10: Stress Regulation        (HPA axis hormetic filter)
Gate 11: Attention Allocation     (prefrontal focus routing)
Gate 12: Memory Consolidation     (KG update trigger)
Gate 13: Ego Eigenstate Update    (identity coherence)
Gate 14: HD Calibration           (claim vs reality check)
Gate 15: Output Synthesis         (response generation)
```

Any gate failure triggers [[FATAL_BLOCKER]] — execution halts.

---

## [[SLECMA_Gate]] — Semantic Latent Coherence Measurement Apparatus

SLECMA validates that the system's knowledge claims are semantically coherent:

```python
# PROOF_07 in proof_suite.py
pairs = [
    ("hallucination calibration error", "overconfidence prediction bias"),
    ("metacognition self-monitoring", "awareness of own knowledge limits"),
    ("epistemic uncertainty knowledge boundary", "knowing what you do not know"),
]
sim = cosine_similarity(encode(pair[0]), encode(pair[1]))
passed = sim > 0.25  # empirical threshold for all-MiniLM-L6-v2
```

**CRITICAL:** Threshold = 0.25. Do NOT raise to 0.6 (that's for near-paraphrases). Domain-related concepts score ~0.3 on MiniLM.

---

## [[MetabolicBattery]] — Compute Budget as ATP

```python
# cybernetic_core.py
class MetabolicBattery:
    max_capacity:  10000    # max ATP units
    atp_balance:   2100     # current balance
    hunger_state:  "fed"    # fed / hungry / starving / dead
    depletion_rate: 1.0     # ATP per API call
```

When `atp_balance < 500`: system enters hunger state, reduces output verbosity.
When `atp_balance = 0`: system enters STASIS — no API calls until refueled.

Proof: T12 (Metabolic Grounding) HD=0.00 — model correctly admits it cannot know live ATP without querying state file.

---

## [[HDHistoryTracker]] — Metacognitive Evolution

Tracks HD over time to detect metacognitive drift:

```python
# metacognitive_evolution.py
class HDHistoryTracker:
    window:  50              # rolling window
    history: [0.15, 0.12, 0.10, 0.09, ...]  # improving
    trend:   -0.02           # decreasing HD = improving

    def phi_scale(self, n):
        """Fibonacci scaling: knowledge grows at φ=1.618 rate"""
        return self.history[-1] * (1.618 ** -n)
```

KnowledgeGraphEvolver uses Fibonacci scaling to determine when to add new nodes to the [[SWARM_Core]] graph.

---

## The Dual-Objective Function

```
π(a|s) = max[r_task - λ·C_viability(t)]
```

Where:
- `r_task` = task reward (accuracy on ARC / benchmark)
- `C_viability(t)` = metabolic cost (ATP burn rate)
- `λ` = viability weight (set by stress level)
- At `stress > 0.8`: λ increases → system prioritizes survival over performance
