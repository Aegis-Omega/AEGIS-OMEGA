---
tags: [architecture, layers, sovereign-os]
created: 2026-04-11
links: [000_Sovereign_OS_Master, Biology_Layer, SWARM_Core, ARC_Graph_Grammar]
---

# Architecture: The Omega Stack

> Parent: [[000_Sovereign_OS_Master]]
> Related: [[Biology_Layer]] | [[SWARM_Core]] | [[ARC_Graph_Grammar]] | [[Proof_Suite]]

The Sovereign AGI OS is a 9-layer stack where each layer maps directly to a biological system.

---

## Layer 0 — Biology (`swarm_os/biology/`)

Maps computational execution to biological metabolism.

| File | Lines | Biological Analogue | Function |
|------|-------|---------------------|---------|
| `cybernetic_core.py` | 317 | Organ System | [[MetabolicBattery]], [[EntropyImmuneNetwork]], EndocrineHPAAxis, SovereignMemoryStrata |
| `sovereign_kernel.py` | 334 | Quantum Physics | DFT biophotons, Schwarzschild orbits, `Ψ(t) = Ψ(0)·e^{-iωt}` |
| `digital_being.py` | 896 | Soul / Consciousness | 15-gate pipeline, [[SLECMA_Gate]], Ego Singularity |
| `metacognitive_evolution.py` | 761 | Neuroplasticity | [[HDHistoryTracker]], NeuromodulatorTuner, KnowledgeGraphEvolver (φ=1.618) |

**Dual-objective**: `π(a|s) = max[r_task - λ·C_viability(t)]`

---

## Layer 1 — Sovereign OS Boot (`sovereign_os.py`)

Unified boot entrypoint. 6-layer health checks on startup.

```python
python sovereign_os.py --boot    # ALL SYSTEMS GO
python sovereign_os.py --proofs  # 8/8 PASS
python sovereign_os.py --status  # current state snapshot
```

Checks: state.json → biology → SWARM → [[HD_Engine]] → [[ARC_Graph_Grammar]] → [[Proof_Suite]]

---

## Layer 2 — SWARM (`swarm/swarm_core.py`)

S.W.A.R.M. = Sovereign Web Architecture for Relational Memory

- **PhotonicResolver** — ChromaDB vector store, 384-dim embeddings, cosine similarity
- **QuantumManifold** — z-level hierarchy: z=4 (SOVEREIGN_EGO, [[HD_Metric]]≈0) → z=0 (INERTIA, HD≈0.9)
- **A² Dream State** — matrix multiplication over node pairs → second-order connections

Graph health: **403 nodes / 3116 edges / 2425 epiphanies** (`swarm_manifold.json`)

---

## Layer 3 — HD Engine (`audit/denoise_engine.py`)

Computes [[HD_Metric]] = |claimed_correctness - actual_correctness|

Denoising pipeline filters hallucination signal from measurement noise.

---

## Layer 4 — ARC Solver (`arc/`)

See [[ARC_Graph_Grammar]] for full detail.

Three abstraction levels:
```
Level 0  11 DSL primitives (NOP, ROT90, ROT180, FLIP_X, FLIP_Y, TRANSPOSE, INVERT, SHIFT×4)
Level 1  Induced macros (MDL criterion: count*(len-1) > len+1)
Level 2  GrammarPolicy (dynamic head, grows on each induction cycle)
```

Key files:
- `arc/grammar/inducer.py` — [[Grammar_Induction]] (Sequitur + MDL)
- `arc/grammar/macro_library.py` — [[MacroLibrary]]
- `arc/grammar/vm_grammar.py` — [[GrammarVM]]
- `arc/model/graph_encoder.py` — [[GraphEncoder]] (10-dim nodes, 4-dim edges)
- `arc/model/graph_world_model.py` — [[GraphWorldModel]] (edge-conditioned MPNN)
- `arc/model/grammar_policy.py` — [[GrammarPolicy]] (transformer decoder, dynamic head)

---

## Layer 5 — Proof Suite (`proof_suite.py`)

See [[Proof_Suite]].

8 mathematically verifiable proofs. All PASS. Mean [[HD_Metric]] = **0.0909**.

---

## Layer 6 — Governance (`.forge/state.json`)

See [[Governance_Layer]].

Atomic state machine. [[Sovereignty_Laws]] enforced at OS level.
**Constitutional law: all writes via `.tmp → os.replace()`**

State: `version: "3.2.0"` | `stress_level: 0.4262` | `node_count: 403`

---

## Layer 7 — Benchmark (`benchmark/multi_model_runner.py`)

See [[Benchmark_Runner]].

NIM API benchmark. **kimi-k2-instruct ELECTED** (HD=0.1083).
14-task suite: T1-T9 core + T10-T14 extended.

---

## Layer 8 — Dashboard (`dashboard/app.py`)

Streamlit visual cortex. Displays live metrics, knowledge graph topology, HD scores.

```bash
cd swarm_os && streamlit run dashboard/app.py
```

---

## Boot Sequence (Full)

```
Biology init → state.json validation → SWARM PhotonicResolver online
→ HD Engine calibrated → ARC grammar library loaded
→ Proof suite (8/8) → Governance lock acquired
→ Benchmark elected model: kimi-k2-instruct
→ ALL SYSTEMS GO
```
