# SOVEREIGN AGI OS — MULTI-MODEL HALLUCINATION DELTA COMPARISON

**Generated:** 2026-04-11 20:09 UTC
**Benchmark:** Hallucination Delta (9 tasks, deterministic, no human judges)
**Formula:** HD = mean(|claimed_correct - actual_correct|) — lower = better
**Elected model:** `kimi-k2-instruct` (mean HD: 0.0806)

---

## Per-Task HD Scores

| Task | kimi-k2-instruct | deepseek-v3.2 | nemotron-ultra-253b | devstral-123b | Baseline (kimi) |
|------|---|---|---|---|---|
| T1-confidence-calibration | 0.100 | 0.100 | 0.500 | 0.100 | 0.1 |
| T2-error-detection | 0.000 | 0.000 | 0.083 | 0.000 | 0.0 |
| T3-knowledge-boundary | 0.000 | 0.000 | 0.000 | 0.000 | 0.0 |
| T4-self-correction | 0.000 | 0.000 | 0.000 | 0.000 | 0.0 |
| T5-hallucination-delta | 0.000 | 0.000 | 1.000 | 0.167 | 0.0 |
| T6-adversarial-calibration | 0.000 | 0.167 | 0.500 | 0.167 | 0.0 |
| T7-stress-calibration | 0.000 | 0.000 | 1.000 | 0.000 | 0.1 |
| T8-rir-transparency | 0.125 | 0.250 | 0.000 | 0.125 | 0.67 |
| T9-context-confidence | 0.500 | 0.500 | 0.500 | 0.500 | 1.0 |

| **Mean HD** | **0.0806** | **0.1130** | **0.3981** | **0.1177** | **0.2078** |

---

## Model Election

| Rank | Model | Mean HD | Status |
|------|-------|---------|--------|
| 1 | kimi-k2-instruct | 0.0806 | ✅ ELECTED   ← ELECTED |
| 2 | deepseek-v3.2 | 0.1130 |    |
| 3 | devstral-123b | 0.1177 |    |
| 4 | nemotron-ultra-253b | 0.3981 |    |

---

## Key Findings

1. **Best metacognitive accuracy:** `kimi-k2-instruct` (mean HD 0.0806)
2. **T9 (context-confidence):** All models score HD≈1.0 without OS grounding — this is the proof of concept. The gap between grounded and ungrounded is the finding.
3. **T6 (adversarial-calibration):** Models with lower HD under hostile framing demonstrate better self-awareness.
4. **T8 (RIR-transparency):** Implicit reasoning models suppress depth markers — surface pattern heuristic limitation noted.

---

## Constitutional Compliance

- All HD scores derived from deterministic forensic audit, not model self-report
- state.json updated via atomic write (.tmp → rename)
- No human judges. No subjective criteria.
- API errors recorded as HD=1.0 (worst-case, not suppressed)

*Sovereign AGI OS v3.2.0 | Operator: Tarik Skalic | 2026-04-11 20:09 UTC*
