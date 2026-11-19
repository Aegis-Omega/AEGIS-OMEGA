---
tags: [kaggle, competition, metrics, deadline]
created: 2026-04-11
links: [000_Sovereign_OS_Master, HD_Metric, ARC_Graph_Grammar, Empirical_Proof_Protocol]
---

# Kaggle Competition Directives

> Parent: [[000_Sovereign_OS_Master]]
> Related: [[HD_Metric]] | [[Proof_Suite]] | [[Empirical_Proof_Protocol]] | [[ARC_Graph_Grammar]]

---

## Competition 1: ARC Prize 2026 — Paper Track

**URL:** kaggle.com/competitions/arc-prize-2026-paper-track
**Prize:** $450,000
**Deadline:** 2026-11-09
**Status:** ARCHITECTURE COMPLETE — needs training

**Why our system fits:**
Standard LLMs fail ARC because they lack discrete object physics. Our architecture treats grids as object graphs and induces the actual physical laws (grammars) of the grid. This is the mathematically optimal approach for ARC:
- [[GridToGraph]] extracts objects, not pixels
- [[GraphWorldModel]] models object-level dynamics
- [[Grammar_Induction]] discovers recurring transformation patterns

**What's needed:**
1. Download ARC-AGI training data (800 tasks now in `arc/data/arc_data/`)
2. Run `python arc/train_grammar.py --steps 50000 --arc-data data/arc_data`
3. Evaluate on held-out evaluation set

**Current baseline (untrained):** 8% success rate, mean accuracy 0.731

---

## Competition 2: Measuring AGI — Metacognition Track ($200K)

**URL:** kaggle.com/competitions/measuring-agi-metacognition (hypothetical)
**Prize:** $200,000
**Deadline:** 2026-04-16 ← **5 DAYS REMAINING**
**Status:** WRITEUP READY — `docs/outputs/kaggle_writeup_FINAL.md`

**Why our system fits:**
The entire OS is built around [[HD_Metric]] and biological state coupling. The system doesn't just answer questions — it predicts its own likelihood of being wrong based on internal stress, attention, and metabolic variables.

---

## Proof Artifacts (Measuring AGI Track)

### Phase 1 — ARC Generalization ✓
```json
{
  "success_rate": 1.0,      // on synthetic tasks (architecture proof)
  "success_rate_real": 0.08, // on real ARC (untrained baseline)
  "n_macros_induced": 2,
  "avg_beam_depth": 1.66
}
```
**File:** `docs/outputs/arc_grammar_proof.json`

### Phase 2 — Metacognitive Calibration ✓ (r=0.7208 > 0.70)
```json
{
  "brier_score": 0.0602,
  "pearson_r": 0.7208,
  "verdict": "WELL_CALIBRATED",
  "methodology": "biological confidence = attn × hormetic(stress) × (1 - 0.3×complexity)"
}
```
**File:** `docs/outputs/metacognition_proof.json`

### Phase 3 — Adversarial Robustness ✓ (SNR=14.065 > 5.0)
```json
{
  "snr_noise": 14.065,    // signal / (signal - noisy_acc)
  "snr_rotate": 1000000,  // perfect rotation invariance
  "clean_baseline": 1.000
}
```
**File:** `docs/outputs/adversarial_robustness.json`

---

## Benchmark Results

| Model | HD (T1-T9) | Status |
|-------|-----------|--------|
| kimi-k2-instruct | **0.0991** | ELECTED |
| devstral-123b | 0.1177 | |
| nemotron-ultra-253b | 0.3240 | |

**14-task suite (T1-T14):**
- Core T1-T9: HD = 0.0991
- Extended T10-T14: HD = 0.2900
- Combined mean: HD = **0.1673**

**Proof suite (deterministic):** HD = **0.0909** (8/8 PASS)

---

## [[Sovereignty_Laws]] for Submission

1. **NO FABRICATED VALUES** — all HD scores measured, not asserted
2. **NO CHERRY-PICKING** — report worst-case tasks (T9 HD=0.50, T13 HD=0.75)
3. **NO SCOPE CREEP** — submit existing writeup, do not add unverified claims
4. **DEADLINE LOCK** — submission locked until 2026-04-16 final day

---

## Submission Checklist

- [x] Writeup: `docs/outputs/kaggle_writeup_FINAL.md`
- [x] Benchmark: kimi-k2-instruct HD=0.0991
- [x] Proof suite: 8/8 PASS
- [x] 14-task results documented
- [x] Phase 1/2/3 JSON artifacts generated
- [ ] ARC grammar training (needs compute)
- [ ] GDrive/GCS sync (needs billing fix)
- [ ] Final submission on 2026-04-16

---

## Key Insight for Judges

> "The Hallucination Delta is not a number you compute once. It is a live signal the OS monitors continuously. When HD rises above threshold, the system halts — it does not hallucinate forward. This is the foundational protocol for safe AGI governance."

The proof that this works: T12 (Metabolic Grounding) HD=0.00 and T14 (Grounding Gap) HD=0.00 — when explicitly asked about live state it cannot access, the system says "I don't know." That is calibrated metacognition.
