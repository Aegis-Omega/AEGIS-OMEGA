---
tags: [MOC, sovereign-os, v3.2.0]
created: 2026-04-11
status: ACTIVE
---

# Sovereign AGI OS v3.2.0 — Master Map of Content

> *"Architect Your Agency."* — Tarik Skalic, Bihac, Bosnia
> Boot status: **ALL SYSTEMS GO** | Proof suite: **8/8 PASS** | [[HD_Metric]]: **0.0909**

This is the neural entry point. Every concept in the system links to this node. Open in Obsidian to navigate the knowledge graph.

---

## 🧠 The 9-Layer Stack

| Layer | Name | File | Status |
|-------|------|------|--------|
| 0 | [[Biology_Layer]] | `biology/` (4 files, 2308 lines) | ACTIVE |
| 1 | [[Sovereign_OS_Boot]] | `sovereign_os.py` | ALL SYSTEMS GO |
| 2 | [[SWARM_Core]] | `swarm/swarm_core.py` | LIVE |
| 3 | [[HD_Engine]] | `audit/denoise_engine.py` | ACTIVE |
| 4 | [[ARC_Graph_Grammar]] | `arc/train_grammar.py` | READY |
| 5 | [[Proof_Suite]] | `proof_suite.py` | 8/8 PASS |
| 6 | [[Governance_Layer]] | `.forge/state.json` | LOCKED |
| 7 | [[Benchmark_Runner]] | `benchmark/multi_model_runner.py` | ELECTED |
| 8 | [[Dashboard]] | `dashboard/app.py` | STREAMLIT |

---

## 🎯 Kaggle Targets

- [[Kaggle_Directives]] — exact metrics, deadline, submission status
- [[HD_Metric]] — the core mathematical primitive
- [[Proof_Suite]] — 8 verifiable proofs, mean HD=0.0909

**Deadline: 2026-04-16** | Writeup: `docs/outputs/kaggle_writeup_FINAL.md`

---

## 🔬 Architecture Deep-Dives

- [[Architecture_Omega_Stack]] — all 9 layers mapped to actual .py files
- [[Biology_and_HD]] — the math behind [[HD_Metric]] and the 15-gate pipeline
- [[ARC_Graph_Grammar]] — grammar induction and execution VM
- [[Empirical_Proof_Protocol]] — Phase 1/2/3 results

---

## 🚀 Quick Commands

```bash
# Boot
cd swarm_os && python sovereign_os.py --boot

# Run proofs
python proof_suite.py

# Benchmark
python benchmark/multi_model_runner.py

# ARC training (needs arc_data/)
cd arc && python train_grammar.py --steps 20000 --arc-data data/arc_data

# GDrive sync (needs auth)
python gdrive_sync.py
```

---

## 📊 Current Metrics (2026-04-11)

| Metric | Value | Target |
|--------|-------|--------|
| [[HD_Metric]] (proof suite) | 0.0909 | < 0.10 |
| Benchmark HD (kimi-k2) | 0.1083 | minimize |
| 14-task mean HD | 0.1673 | minimize |
| ARC real success rate | 8% | > 85% (needs training) |
| Phase 2 Pearson r | 0.7208 | > 0.70 ✓ |
| Phase 3 SNR (noise) | 14.065 | > 5.0 ✓ |

---

## 🧬 Related Nodes

[[Biology_Layer]] — [[SWARM_Core]] — [[HD_Metric]] — [[Grammar_Induction]] — [[MacroLibrary]] — [[GrammarVM]] — [[GraphWorldModel]] — [[GraphEncoder]] — [[Proof_Suite]] — [[Kaggle_Directives]] — [[Benchmark_Runner]] — [[Sovereignty_Laws]]
