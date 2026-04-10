"""
ARC v3 — Grid Encoder
Encodes padded 30×30 ARC grids (input + output pair) into a latent vector.
Input pair is stacked: [input_grid, output_grid] → 2×30×30 = 1800 features.
"""

import torch
import torch.nn as nn
from config import GRID_MAX, EMBED_DIM


class Encoder(nn.Module):
    def __init__(self, d: int = EMBED_DIM):
        super().__init__()
        in_dim = GRID_MAX * GRID_MAX  # 900 per grid, single grid encoding
        self.net = nn.Sequential(
            nn.Linear(in_dim, d * 2),
            nn.LayerNorm(d * 2),
            nn.ReLU(),
            nn.Linear(d * 2, d),
            nn.LayerNorm(d),
            nn.ReLU(),
            nn.Linear(d, d),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, H, W) int64 grid — padded to GRID_MAX×GRID_MAX
        returns: (B, d) float latent
        """
        x = x.float() / 9.0   # normalize to [0,1]
        x = x.view(x.size(0), -1)  # (B, 900)
        return self.net(x)
