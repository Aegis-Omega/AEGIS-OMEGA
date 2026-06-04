"""
SOVEREIGN OMEGA — ICA/NMF Source Attribution
EPISTEMIC TIER: T2 (engineering hypothesis — algorithm validated, AEGIS integration pending)
DETERMINISM CLASS: observational (no write-back to governance state)

Sliding-window NMF that disentangles overlapping telemetry signals into three
causal sources: GPU inference, governance computation (PGCS/TGCS), and OS noise.

Sequence numbers drive the sliding window — never wall-clock time — preserving
replay-safety. The decomposition can be re-run from the event log and produce
identical attribution results.

ICA/NMF SKILL — T2→T1 promotion criteria (first step):
  Implement sliding-window NMF in python/source_attribution.py.
  T1 requires: ≥3 independent runs correctly identify source of corruption_count spike.

DEPENDENCY: bridge.py wires this in at the /telemetry endpoint as optional
  source_attribution field, attached only when a full window is available.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

try:
    import numpy as np
    from sklearn.decomposition import NMF as _NMF
    _NMF_AVAILABLE = True
except ImportError:  # pragma: no cover — sklearn optional
    _NMF_AVAILABLE = False

# Window size matches VCG_WINDOW_SIZE so attribution epochs are comparable to
# calibration epochs. Must not use time.time() — sequence numbers are the clock.
VCG_WINDOW_SIZE = 500
_N_COMPONENTS = 3   # gpu_inference · governance · os_noise
_COMPONENT_LABELS = ('gpu_inference', 'governance', 'os_noise')


@dataclass(frozen=True)
class TelemetrySample:
    """One telemetry snapshot fed into the attribution buffer."""
    sequence: int
    # GPU inference load proxy: AFSE holonic scaling score (0–1, non-negative)
    afse_score: float
    # Governance computation proxy: TGCS cycle stretch (non-negative ms)
    tgcs_stretch_ms: float
    # PGCS disk pressure proxy: compressed bytes written this window (non-negative)
    pgcs_compressed_bytes: int


@dataclass(frozen=True)
class SourceAttribution:
    """
    NMF-decomposed attribution fractions (sum ≈ 1.0, each ≥ 0).
    These are observational estimates — they inform diagnostics only.
    They do not affect t0_verdict, corruption_count, or governance state.
    """
    gpu_inference: float
    governance: float
    os_noise: float
    window_size: int        # actual samples used (may be < VCG_WINDOW_SIZE early on)
    sequence_start: int     # sequence number of the oldest sample in this window
    sequence_end: int       # sequence number of the newest sample in this window
    determinism_class: str  # always 'observational'

    def to_dict(self) -> Dict[str, object]:
        return {
            'gpu_inference': round(self.gpu_inference, 4),
            'governance': round(self.governance, 4),
            'os_noise': round(self.os_noise, 4),
            'window_size': self.window_size,
            'sequence_start': self.sequence_start,
            'sequence_end': self.sequence_end,
            'determinism_class': self.determinism_class,
        }


class SourceAttributor:
    """
    Maintains a sliding window of TelemetrySamples and applies NMF decomposition
    to attribute variance to three independent sources.

    Thread-safety: caller is responsible for external locking if used from multiple
    threads (bridge.py holds _lock around telemetry reads).
    """

    def __init__(self, window_size: int = VCG_WINDOW_SIZE) -> None:
        self._window_size = window_size
        self._buf: Deque[TelemetrySample] = deque(maxlen=window_size)

    def push(self, sample: TelemetrySample) -> None:
        """Append one telemetry sample; oldest is automatically evicted at capacity."""
        self._buf.append(sample)

    def attribute(self) -> Optional[SourceAttribution]:
        """
        Run NMF over the current window and return attribution fractions.

        Returns None when:
          - sklearn is unavailable
          - fewer than 3 samples in buffer (NMF needs ≥ n_components rows)
          - all signals are zero (degenerate window — e.g. idle system)
        """
        if not _NMF_AVAILABLE or len(self._buf) < _N_COMPONENTS:
            return None

        samples = list(self._buf)
        n = len(samples)

        # Build signal matrix: shape (n, 3) — each column one signal source proxy.
        # All values are non-negative by construction; NMF constraint satisfied.
        matrix = np.array([
            [s.afse_score, s.tgcs_stretch_ms, float(s.pgcs_compressed_bytes)]
            for s in samples
        ], dtype=np.float64)

        # Guard: degenerate window (all signals zero → no variance to decompose)
        if matrix.max() == 0.0:
            return None

        # Normalise columns to [0,1] so no single signal dominates by scale.
        col_max = matrix.max(axis=0)
        col_max[col_max == 0.0] = 1.0  # prevent division by zero on dead columns
        matrix = matrix / col_max

        nmf = _NMF(n_components=_N_COMPONENTS, max_iter=300, random_state=42)
        try:
            W = nmf.fit_transform(matrix)  # shape (n, 3) — mixing weights
        except Exception:  # pragma: no cover — NMF convergence failure is rare
            return None

        # Average mixing weight per component across all window samples.
        mean_w = W.mean(axis=0)
        total = mean_w.sum()
        if total == 0.0:
            return None
        fractions = mean_w / total  # normalise to attribution fractions summing to 1.0

        return SourceAttribution(
            gpu_inference=float(fractions[0]),
            governance=float(fractions[1]),
            os_noise=float(fractions[2]),
            window_size=n,
            sequence_start=samples[0].sequence,
            sequence_end=samples[-1].sequence,
            determinism_class='observational',
        )
