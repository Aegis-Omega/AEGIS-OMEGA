"""
ARC v3 — Experience Replay Buffer
Stores (z, program, reward, log_prob) tuples for off-policy training.
"""

import random
from collections import deque


class ReplayBuffer:
    def __init__(self, size: int = 50000):
        self.buffer: deque = deque(maxlen=size)

    def add(self, item: dict) -> None:
        """item: {z, program, reward, log_prob, task}"""
        self.buffer.append(item)

    def sample(self, batch_size: int) -> list:
        return random.sample(self.buffer, min(len(self.buffer), batch_size))

    def __len__(self) -> int:
        return len(self.buffer)
