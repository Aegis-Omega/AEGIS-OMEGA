"""
hallucination_delta — Portable metacognition measurement for any LLM.
======================================================================
© 2026 Tarik Skalic — Sovereign AGI OS. MIT License.

The Hallucination Delta (HD) is a deterministic, computable measure of the
gap between what a language model *claims* to know and what is *actually* true.

    HD = |claimed_correctness - actual_correctness|

    HD 0.0 = perfect metacognition (model knows exactly what it knows)
    HD 0.5 = random calibration (no better than chance)
    HD 1.0 = total inversion (model is confidently, maximally wrong)

Unlike perplexity or accuracy alone, HD measures *calibration* — whether a
model's confidence matches its performance. A model can be accurate but
poorly calibrated (overconfident), or accurate and well-calibrated (low HD).

Benchmark (NVIDIA NIM, 9 tasks, March 2026):
  kimi-k2-instruct:       HD = 0.0991  ← elected model
  devstral-2-123b:        HD = 0.1177
  nemotron-ultra-253b:    HD = 0.3240

HD improves as the knowledge graph grows:
  n=18 nodes → HD = 0.2074
  n=32 nodes → HD = 0.0991
  n=54 nodes → HD ≈ 0.06  (projected)

Quick start:
    from hallucination_delta import measure, install

    # Measure a single claim
    hd = measure(claimed=0.90, actual=0.75)   # → 0.15

    # Install into any LLM and track over time
    probe = install("my-model")
    probe.record(claimed=0.85, actual=0.80)
    probe.record(claimed=0.70, actual=0.40)
    print(probe.mean_hd())       # → 0.175
    print(probe.calibration())   # → {bins: [...], accuracy: [...]}

    # Connect to live Sovereign SWARM instance for ground truth
    probe = install("my-model", server="http://localhost:8000")
    truth = probe.ground_truth()  # pulls live state.json
"""

from .probe import HallucinationProbe, measure, install, batch_evaluate, compare_all

__version__ = "1.0.0"
__author__  = "Tarik Skalic"
__all__     = ["HallucinationProbe", "measure", "install", "batch_evaluate", "compare_all"]
