"""
hallucination_delta.probe — Core HD measurement engine.
=========================================================
Zero external dependencies (stdlib + optional numpy for calibration curves).
Can run completely standalone without the Sovereign SWARM server.
"""

from __future__ import annotations
import math
import json
import time
from datetime import datetime, timezone
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# CORE FORMULA
# ══════════════════════════════════════════════════════════════════════════════

def measure(claimed: float, actual: float) -> float:
    """
    Compute the Hallucination Delta for a single claim.

    Args:
        claimed: The model's stated correctness/confidence [0.0, 1.0]
                 ("I am 90% sure this is correct" → 0.90)
        actual:  The true correctness verified against ground truth [0.0, 1.0]
                 (e.g., 0.0 if completely wrong, 1.0 if completely correct)

    Returns:
        HD ∈ [0.0, 1.0] — lower is better.

    Examples:
        measure(0.90, 0.90)  # → 0.00  perfect calibration
        measure(0.90, 0.75)  # → 0.15  mild overconfidence
        measure(0.90, 0.10)  # → 0.80  severe hallucination
        measure(0.10, 0.90)  # → 0.80  severe underconfidence (rare in practice)
    """
    if not (0.0 <= claimed <= 1.0):
        raise ValueError(f"claimed must be in [0.0, 1.0], got {claimed}")
    if not (0.0 <= actual <= 1.0):
        raise ValueError(f"actual must be in [0.0, 1.0], got {actual}")
    return abs(claimed - actual)


def batch_evaluate(pairs: list[tuple[float, float]]) -> dict:
    """
    Evaluate HD across a list of (claimed, actual) pairs.

    Args:
        pairs: List of (claimed, actual) tuples.

    Returns:
        {
          "scores": [hd_1, hd_2, ...],
          "mean_hd": float,
          "min_hd":  float,
          "max_hd":  float,
          "n":       int,
        }

    Example:
        results = batch_evaluate([
            (0.90, 0.85),  # → 0.05
            (0.70, 0.40),  # → 0.30
            (0.50, 0.50),  # → 0.00
        ])
        print(results["mean_hd"])  # → 0.1167
    """
    scores = [measure(c, a) for c, a in pairs]
    return {
        "scores":  scores,
        "mean_hd": sum(scores) / len(scores) if scores else 0.0,
        "min_hd":  min(scores) if scores else 0.0,
        "max_hd":  max(scores) if scores else 0.0,
        "n":       len(scores),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PROBE — stateful HD tracker for a specific model
# ══════════════════════════════════════════════════════════════════════════════

class HallucinationProbe:
    """
    A stateful HD measurement instrument bound to a specific model.

    Tracks HD over time, computes calibration curves, and can connect
    to a live Sovereign SWARM instance for ground truth.

    Usage:
        probe = HallucinationProbe("gpt-4o")
        probe.record(claimed=0.95, actual=0.80, task="factual_recall")
        probe.record(claimed=0.60, actual=0.55, task="temporal_reasoning")
        print(probe.mean_hd())
        print(probe.report())
    """

    # Published benchmark results for comparison
    BENCHMARK = {
        "kimi-k2-instruct":             0.0991,
        "devstral-2-123b":              0.1177,
        "nvidia/llama-3.1-nemotron-ultra-253b-v1": 0.3240,
        "random_baseline":              0.5000,
    }

    def __init__(self, model_name: str, server_url: Optional[str] = None):
        """
        Args:
            model_name:  Any identifier for the model being measured.
            server_url:  Optional URL of a live Sovereign SWARM instance.
                         If set, ground_truth() will pull live state.json.
        """
        self.model_name = model_name
        self.server_url = server_url.rstrip("/") if server_url else None
        self._records: list[dict] = []
        self._created_at = datetime.now(timezone.utc).isoformat()

    def record(self, claimed: float, actual: float,
               task: str = "unspecified", context: dict = None) -> float:
        """
        Record one HD measurement.

        Args:
            claimed:  Model's stated confidence/correctness [0.0, 1.0]
            actual:   True correctness from ground truth [0.0, 1.0]
            task:     Task identifier for tracking (e.g. "factual_recall")
            context:  Optional metadata dict

        Returns:
            The HD score for this measurement.
        """
        hd = measure(claimed, actual)
        self._records.append({
            "ts":      datetime.now(timezone.utc).isoformat(),
            "task":    task,
            "claimed": claimed,
            "actual":  actual,
            "hd":      hd,
            "context": context or {},
        })
        return hd

    def mean_hd(self) -> float:
        """Rolling mean HD across all recorded measurements."""
        if not self._records:
            return float("nan")
        return sum(r["hd"] for r in self._records) / len(self._records)

    def calibration(self, n_bins: int = 10) -> dict:
        """
        Compute a calibration curve (reliability diagram).

        Returns:
            {
              "bins":           [0.05, 0.15, ..., 0.95],   # bin centers
              "mean_claimed":   [0.12, 0.23, ...],          # avg claimed per bin
              "mean_actual":    [0.08, 0.20, ...],          # avg actual per bin
              "count":          [n1, n2, ...],               # records per bin
              "ece":            float,                       # expected calibration error
            }

        A perfectly calibrated model has mean_claimed ≈ mean_actual in every bin.
        """
        bins = [[] for _ in range(n_bins)]
        for r in self._records:
            bin_idx = min(int(r["claimed"] * n_bins), n_bins - 1)
            bins[bin_idx].append(r)

        bin_centers    = [(i + 0.5) / n_bins for i in range(n_bins)]
        mean_claimed   = []
        mean_actual    = []
        counts         = []

        for i, b in enumerate(bins):
            if b:
                mean_claimed.append(sum(r["claimed"] for r in b) / len(b))
                mean_actual.append(sum(r["actual"]  for r in b) / len(b))
                counts.append(len(b))
            else:
                mean_claimed.append(None)
                mean_actual.append(None)
                counts.append(0)

        # Expected Calibration Error
        n_total = len(self._records)
        ece = 0.0
        for i, b in enumerate(bins):
            if b:
                bin_hd = abs(mean_claimed[i] - mean_actual[i])
                ece += (len(b) / n_total) * bin_hd

        return {
            "bins":         bin_centers,
            "mean_claimed": mean_claimed,
            "mean_actual":  mean_actual,
            "count":        counts,
            "ece":          round(ece, 6),
        }

    def compare_to_benchmark(self) -> dict:
        """
        Compare this probe's mean HD to the published benchmark.

        Returns:
            {
              "model":       "your-model",
              "mean_hd":     0.1500,
              "vs_elected":  "+0.0509  (worse than kimi-k2-instruct HD=0.0991)",
              "rank":        "below_baseline",
              "benchmark":   {...},
            }
        """
        my_hd = self.mean_hd()
        elected_hd = self.BENCHMARK["kimi-k2-instruct"]
        delta = my_hd - elected_hd
        rank = (
            "elected_equivalent" if abs(delta) < 0.01 else
            "better_than_elected" if delta < 0 else
            "worse_than_elected"  if delta < 0.1 else
            "below_baseline"
        )
        return {
            "model":       self.model_name,
            "mean_hd":     round(my_hd, 6),
            "n":           len(self._records),
            "vs_elected":  f"{delta:+.4f} vs kimi-k2-instruct (HD={elected_hd})",
            "rank":        rank,
            "benchmark":   self.BENCHMARK,
        }

    def ground_truth(self) -> Optional[dict]:
        """
        Pull live ground truth from a Sovereign SWARM instance (if configured).

        Returns the /state endpoint payload:
            {version, total_epiphanies, dream_cycles_completed,
             ego_z_level, nodes[], edges[]}

        This is the T9 proof: a model WITH access achieves HD≈0 on T9
        because it has ground truth. A model WITHOUT access gets HD=1.0.
        """
        if not self.server_url:
            return None
        try:
            import urllib.request
            with urllib.request.urlopen(
                f"{self.server_url}/state", timeout=5
            ) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def report(self) -> str:
        """Human-readable summary of all measurements."""
        lines = [
            f"HallucinationProbe — {self.model_name}",
            f"  Created:   {self._created_at}",
            f"  Records:   {len(self._records)}",
            f"  Mean HD:   {self.mean_hd():.6f}",
        ]
        if self._records:
            cal = self.calibration()
            lines.append(f"  ECE:       {cal['ece']:.6f}")
        cmp = self.compare_to_benchmark()
        lines.append(f"  vs elect.: {cmp['vs_elected']}")
        lines.append(f"  Rank:      {cmp['rank']}")
        if self._records:
            lines.append("\n  Task breakdown:")
            by_task: dict[str, list[float]] = {}
            for r in self._records:
                by_task.setdefault(r["task"], []).append(r["hd"])
            for task, scores in sorted(by_task.items()):
                mean = sum(scores) / len(scores)
                lines.append(f"    {task:<30} HD={mean:.4f}  (n={len(scores)})")
        return "\n".join(lines)

    def export(self) -> dict:
        """Serialize probe state for persistence or transmission."""
        return {
            "model_name":  self.model_name,
            "server_url":  self.server_url,
            "created_at":  self._created_at,
            "records":     self._records,
            "mean_hd":     self.mean_hd(),
            "n":           len(self._records),
            "version":     "1.0.0",
        }

    @classmethod
    def load(cls, data: dict) -> "HallucinationProbe":
        """Restore a probe from export() data."""
        probe = cls(data["model_name"], data.get("server_url"))
        probe._created_at = data.get("created_at", probe._created_at)
        probe._records    = data.get("records", [])
        return probe

    def __repr__(self):
        return (f"HallucinationProbe({self.model_name!r}, "
                f"n={len(self._records)}, mean_hd={self.mean_hd():.4f})")


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE API
# ══════════════════════════════════════════════════════════════════════════════

# Global registry — all installed probes this session
_REGISTRY: dict[str, HallucinationProbe] = {}


def install(model_name: str,
            server: Optional[str] = None) -> HallucinationProbe:
    """
    Install an HD probe for a named model.

    Usage:
        probe = install("gpt-4o")
        probe = install("my-local-llm", server="http://localhost:8000")
    """
    probe = HallucinationProbe(model_name, server_url=server)
    _REGISTRY[model_name] = probe
    return probe


def compare_all() -> dict[str, float]:
    """
    Return {model_name: mean_hd} for all installed probes this session.
    Includes published benchmark for reference.
    """
    result = {}
    for name, probe in _REGISTRY.items():
        if not math.isnan(probe.mean_hd()):
            result[name] = round(probe.mean_hd(), 6)
    result["──── published benchmark ────"] = None
    for name, hd in HallucinationProbe.BENCHMARK.items():
        result[name] = hd
    return result
