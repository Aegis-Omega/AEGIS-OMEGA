"""
ARC v3 — Self-Play Mutation
Generates input perturbations for CVS computation and curriculum augmentation.
These are not new tasks — they are controlled variations to test program stability.
"""

import random
import numpy as np


def mutate(task: dict) -> dict:
    """
    Apply a random invertible transformation to the input grid.
    The ground-truth output is NOT mutated — the reward will be lower
    unless the learned program is transformation-invariant.
    """
    t = dict(task)
    op = random.randint(0, 3)
    inp = np.array(t["input"], dtype=np.int64)

    if op == 0:
        inp = np.flip(inp, axis=0)   # vertical flip
    elif op == 1:
        inp = np.flip(inp, axis=1)   # horizontal flip
    elif op == 2:
        inp = np.rot90(inp)          # 90° rotation
    elif op == 3:
        inp = np.roll(inp, 1, axis=0)  # shift down 1

    t["input"] = inp
    return t


def perturbations(task: dict, n: int = 3) -> list[dict]:
    """Generate n mutated variants of a task for CVS measurement."""
    return [mutate(task) for _ in range(n)]
