"""
ARC v3 — GraphState
Discrete object-graph representation of an ARC grid.

G = (V, E)
  V: object nodes — each unique connected component of same-color cells
  E: spatial relationships — adjacency, containment, alignment, symmetry
"""

from dataclasses import dataclass
import torch


@dataclass
class GraphState:
    x:          torch.Tensor   # [N, d_node]  node features (encoded)
    edge_index: torch.Tensor   # [2, E]       source/destination indices
    edge_attr:  torch.Tensor   # [E, d_edge]  edge features (encoded)

    def to(self, device) -> "GraphState":
        return GraphState(
            x          = self.x.to(device),
            edge_index = self.edge_index.to(device),
            edge_attr  = self.edge_attr.to(device),
        )

    @property
    def num_nodes(self) -> int:
        return self.x.shape[0]

    @property
    def num_edges(self) -> int:
        return self.edge_attr.shape[0]
