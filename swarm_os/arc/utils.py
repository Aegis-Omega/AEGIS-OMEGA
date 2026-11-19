"""
ARC v3 — Utilities
HD-grounded metrics: accuracy, CVS, MDL.
"""

import numpy as np
from config import GRID_MAX


def pad_grid(grid: np.ndarray) -> np.ndarray:
    """Pad any ARC grid to GRID_MAX×GRID_MAX with zeros."""
    h, w = grid.shape[:2]
    out = np.zeros((GRID_MAX, GRID_MAX), dtype=np.int64)
    out[:min(h, GRID_MAX), :min(w, GRID_MAX)] = grid[:min(h, GRID_MAX), :min(w, GRID_MAX)]
    return out


def accuracy(pred: np.ndarray, target: np.ndarray) -> float:
    """
    Cell-level accuracy between pred and target grids.
    Crops to the smaller of the two before comparing.
    HD_arc = 1 - accuracy  (lower is better).
    """
    h = min(pred.shape[0], target.shape[0])
    w = min(pred.shape[1], target.shape[1])
    pred_c = pred[:h, :w]
    tgt_c  = target[:h, :w]
    return float((pred_c == tgt_c).mean())


def compute_cvs(program_outputs: list) -> float:
    """
    Causal Variance Score: stability of program output under input perturbations.
    High CVS = program captures a stable transformation rule.
    CVS = max(0, 1 - mean_cell_variance_across_outputs)
    """
    if len(program_outputs) < 2:
        return 0.0
    # Stack outputs (each is a flattened grid)
    stacked = np.stack([o.flatten().astype(float) for o in program_outputs])
    mean_var = np.var(stacked, axis=0).mean()
    # Normalize: ARC values in [0,9], max variance = 20.25
    return float(max(0.0, 1.0 - mean_var / 20.25))


def compute_mdl(program: np.ndarray) -> int:
    """
    Minimum Description Length proxy: effective program length.
    NOP tokens (op=0) are free — count only non-NOP ops.
    """
    return int(np.sum(program != 0))
