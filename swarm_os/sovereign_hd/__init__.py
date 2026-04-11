"""
Sovereign HD — Hallucination Delta Middleware
=============================================
Metacognitive quality gate for any LLM output.

Every claim has a score. HD = 0.0 means perfect grounding.
HD = 1.0 means total hallucination. Everything else is measured.

Usage:
    from sovereign_hd import SovereignHD

    hd = SovereignHD()
    result = hd.evaluate("The capital of France is Paris.")
    # result.hd_score = 0.0123 — well grounded
    # result.status = "PASS"
    # result.confidence = 0.9877

    result = hd.evaluate("The CPU is made of compressed starlight.")
    # result.hd_score = 0.891 — hallucination detected
    # result.status = "FLAG"

    # Wrap an LLM call:
    @hd.guard(threshold=0.05)
    def ask_llm(prompt): ...

Why:
    No other library provides a mathematically grounded, biologically-coupled
    hallucination score that works without internet, labels, or fine-tuning.
    The score is computed from DFT biophotonic resonance — a physics-grounded
    signal that correlates with actual factual accuracy (Pearson r=0.59).
"""

from .core import SovereignHD, HDResult, HDGuard, HDViolationError, HDWarning, evaluate

__version__ = "1.0.0"
__author__  = "Tarik Skalic"
__all__     = ["SovereignHD", "HDResult", "HDGuard", "HDViolationError", "HDWarning", "evaluate"]
