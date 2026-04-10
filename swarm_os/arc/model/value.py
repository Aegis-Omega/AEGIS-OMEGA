"""
ARC v3 — Value Network
Estimates expected return V(z) for advantage computation in PPO.
"""

import torch.nn as nn
from config import EMBED_DIM


class Value(nn.Module):
    def __init__(self, d: int = EMBED_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d, d),
            nn.LayerNorm(d),
            nn.ReLU(),
            nn.Linear(d, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, z):
        """z: (B, d) → (B,) value estimates"""
        return self.net(z).squeeze(-1)
