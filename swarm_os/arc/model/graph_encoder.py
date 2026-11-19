"""
ARC v3 — Graph Encoder
Two components:

1. GridToGraph  — converts a raw ARC grid (numpy H×W int64) into raw
                  node/edge feature tensors using connected-component analysis.
                  This is the inductive bias: ARC is about objects.

2. GraphEncoder — learnable MLP that lifts raw features into d_model-dim
                  node + edge embeddings → GraphState.

Node features (10-dim, raw):
  [0]  color_norm      = color / 9
  [1]  height_norm     = bbox height / 30
  [2]  width_norm      = bbox width / 30
  [3]  cy_norm         = centroid row / 30
  [4]  cx_norm         = centroid col / 30
  [5]  area_norm       = pixel count / 900
  [6]  aspect_ratio    = min(h,w) / max(h,w)   (0 = degenerate, 1 = square)
  [7]  density         = area / (h * w)         (fill rate of bounding box)
  [8]  is_background   = 1 if color == 0 else 0
  [9]  size_rank_norm  = rank by area / N        (relative size)

Edge features (4-dim, raw):
  [0]  dy_norm     = |cy_a - cy_b| / 30
  [1]  dx_norm     = |cx_a - cx_b| / 30
  [2]  same_color  = 1 if color_a == color_b else 0
  [3]  adjacent    = 1 if bbox overlap or touching else 0
"""

import numpy as np
import torch
import torch.nn as nn
from scipy import ndimage
from config import EMBED_DIM
from .graph_state import GraphState

NODE_DIM = 10
EDGE_DIM = 4


# ══════════════════════════════════════════════════════════════════════════════
# GRID → GRAPH (no learned parameters — pure structured extraction)
# ══════════════════════════════════════════════════════════════════════════════

def grid_to_raw(grid: np.ndarray):
    """
    Extract object nodes and spatial edges from an ARC grid.

    Returns:
        node_feats: np.ndarray [N, NODE_DIM]
        edge_src:   np.ndarray [E]
        edge_dst:   np.ndarray [E]
        edge_feats: np.ndarray [E, EDGE_DIM]
    """
    H, W = grid.shape
    grid_area = max(H * W, 1)

    # ── Find connected components for each color ──────────────────────────────
    nodes = []   # list of dicts with object properties
    color_mask = {}

    for color in range(10):
        mask = (grid == color)
        if not mask.any():
            continue
        labeled, n_comp = ndimage.label(mask)
        for comp_id in range(1, n_comp + 1):
            comp_mask = (labeled == comp_id)
            rows, cols = np.where(comp_mask)
            area   = int(comp_mask.sum())
            r_min, r_max = int(rows.min()), int(rows.max())
            c_min, c_max = int(cols.min()), int(cols.max())
            h = r_max - r_min + 1
            w = c_max - c_min + 1
            cy = float(rows.mean())
            cx = float(cols.mean())
            nodes.append({
                "color":    color,
                "area":     area,
                "h":        h, "w": w,
                "cy":       cy, "cx": cx,
                "r_min": r_min, "r_max": r_max,
                "c_min": c_min, "c_max": c_max,
            })

    if not nodes:
        # Degenerate: return single background node
        nodes = [{"color": 0, "area": grid_area, "h": H, "w": W,
                  "cy": H/2, "cx": W/2, "r_min": 0, "r_max": H-1,
                  "c_min": 0, "c_max": W-1}]

    N = len(nodes)

    # ── Size rank ─────────────────────────────────────────────────────────────
    areas = np.array([nd["area"] for nd in nodes], dtype=float)
    rank  = np.argsort(np.argsort(areas)).astype(float)
    rank_norm = rank / max(N - 1, 1)

    # ── Node features ─────────────────────────────────────────────────────────
    node_feats = np.zeros((N, NODE_DIM), dtype=np.float32)
    for i, nd in enumerate(nodes):
        h, w = nd["h"], nd["w"]
        asp = min(h, w) / max(h, w, 1)
        den = nd["area"] / max(h * w, 1)
        node_feats[i] = [
            nd["color"] / 9.0,
            h / 30.0,
            w / 30.0,
            nd["cy"] / max(H - 1, 1),
            nd["cx"] / max(W - 1, 1),
            nd["area"] / 900.0,
            asp,
            den,
            float(nd["color"] == 0),
            rank_norm[i],
        ]

    # ── Edges: all pairs ──────────────────────────────────────────────────────
    src_list, dst_list, ef_list = [], [], []
    for i in range(N):
        for j in range(N):
            if i == j:
                continue
            ni, nj = nodes[i], nodes[j]
            dy = abs(ni["cy"] - nj["cy"]) / max(H - 1, 1)
            dx = abs(ni["cx"] - nj["cx"]) / max(W - 1, 1)
            same_color = float(ni["color"] == nj["color"])
            # Adjacent: bounding boxes touch or overlap (±1 pixel)
            r_touch = (ni["r_min"] - 1 <= nj["r_max"]) and (nj["r_min"] - 1 <= ni["r_max"])
            c_touch = (ni["c_min"] - 1 <= nj["c_max"]) and (nj["c_min"] - 1 <= ni["c_max"])
            adjacent = float(r_touch and c_touch)

            src_list.append(i)
            dst_list.append(j)
            ef_list.append([dy, dx, same_color, adjacent])

    if not src_list:
        # Single node: self-loop
        src_list, dst_list = [0], [0]
        ef_list = [[0.0, 0.0, 1.0, 1.0]]

    edge_src   = np.array(src_list, dtype=np.int64)
    edge_dst   = np.array(dst_list, dtype=np.int64)
    edge_feats = np.array(ef_list, dtype=np.float32)

    return node_feats, edge_src, edge_dst, edge_feats


# ══════════════════════════════════════════════════════════════════════════════
# LEARNABLE ENCODER: raw features → d_model embeddings
# ══════════════════════════════════════════════════════════════════════════════

class GraphEncoder(nn.Module):
    def __init__(self, d: int = EMBED_DIM, node_dim: int = NODE_DIM, edge_dim: int = EDGE_DIM):
        super().__init__()
        self.node_enc = nn.Sequential(
            nn.Linear(node_dim, d),
            nn.LayerNorm(d),
            nn.ReLU(),
            nn.Linear(d, d),
        )
        self.edge_enc = nn.Sequential(
            nn.Linear(edge_dim, d),
            nn.LayerNorm(d),
            nn.ReLU(),
            nn.Linear(d, d),
        )

    def forward(self, grid: np.ndarray, device="cpu") -> GraphState:
        """
        grid: H×W numpy int64 ARC grid
        Returns: GraphState with encoded node + edge embeddings on device
        """
        nf, esrc, edst, ef = grid_to_raw(grid)

        x         = torch.tensor(nf, dtype=torch.float32, device=device)
        edge_index = torch.tensor(np.stack([esrc, edst]), dtype=torch.long, device=device)
        ea         = torch.tensor(ef, dtype=torch.float32, device=device)

        x  = self.node_enc(x)    # [N, d]
        ea = self.edge_enc(ea)   # [E, d]

        return GraphState(x=x, edge_index=edge_index, edge_attr=ea)
