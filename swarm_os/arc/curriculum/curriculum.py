"""
ARC v3 — Curriculum
Adaptive difficulty scheduler based on rolling reward window.
"""

from collections import deque
import numpy as np


class Curriculum:
    def __init__(self, window: int = 50, threshold: float = 0.7):
        self.level = 1
        self.window = window
        self.threshold = threshold
        self._rewards: deque = deque(maxlen=window)

    def update(self, reward: float) -> bool:
        """Record reward. Returns True if level advanced."""
        self._rewards.append(reward)
        if len(self._rewards) == self.window:
            avg = np.mean(self._rewards)
            if avg >= self.threshold:
                self.level += 1
                self._rewards.clear()
                return True
        return False

    @property
    def mean_reward(self) -> float:
        if not self._rewards:
            return 0.0
        return float(np.mean(self._rewards))

    def apply(self, task: dict) -> dict:
        """
        At higher levels, mask easy tasks — currently a pass-through.
        Level 1: all tasks. Level 2+: could filter to multi-step tasks.
        """
        return task
