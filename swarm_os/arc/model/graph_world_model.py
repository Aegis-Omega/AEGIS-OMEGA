"""
ARC v3 — Graph World Model
G_{t+1} = F(G_t, A_t)

Learned dynamics via edge-conditioned message passing:
  1. Inject action globally into all nodes
  2. Compute messages along edges (src + dst + edge_attr)
  3. Aggregate messages at each destination node
  4. Update node features: h_new = MLP([h_old, aggregated_messages])
  5. Predict reward from mean-pooled graph embedding

This is the replacement for vector state prediction.
Object identity is preserved — no semantic collapse under small errors.
"""

import torch
import torch.nn as nn
from .graph_state import GraphState
from config import EMBED_DIM, VOCAB_SIZE


class GraphWorldModel(nn.Module):
    def __init__(self, d: int = EMBED_DIM):
        super().__init__()

        # Action embedding (DSL op → d-dim vector)
        self.action_emb = nn.Embedding(VOCAB_SIZE, d)

        # Action injection: condition each node on the action
        self.action_proj = nn.Sequential(
            nn.Linear(d, d),
            nn.ReLU(),
        )

        # Edge-conditioned message function: f(h_src, h_dst, e_attr)
        self.msg_mlp = nn.Sequential(
            nn.Linear(d * 3, d * 2),
            nn.LayerNorm(d * 2),
            nn.ReLU(),
            nn.Linear(d * 2, d),
        )

        # Node update: g(h_old, aggregated_messages)
        self.node_mlp = nn.Sequential(
            nn.Linear(d * 2, d),
            nn.LayerNorm(d),
            nn.ReLU(),
            nn.Linear(d, d),
        )

        # Reward head: scalar from mean-pooled graph
        self.reward_head = nn.Sequential(
            nn.Linear(d, d // 2),
            nn.ReLU(),
            nn.Linear(d // 2, 1),
        )

    def forward(self, graph: GraphState, action: torch.Tensor) -> tuple[GraphState, torch.Tensor]:
        """
        graph:  GraphState (x: [N,d], edge_index: [2,E], edge_attr: [E,d])
        action: LongTensor scalar or [1] — DSL op index

        Returns:
            next_graph: GraphState (updated node features, same topology)
            reward:     scalar Tensor
        """
        x          = graph.x                    # [N, d]
        edge_index = graph.edge_index           # [2, E]
        edge_attr  = graph.edge_attr            # [E, d]
        src, dst   = edge_index[0], edge_index[1]

        # 1. Inject action into all nodes
        a   = self.action_emb(action.view(1)).squeeze(0)   # [d]
        a_p = self.action_proj(a)                           # [d]
        x_a = x + a_p.unsqueeze(0)                         # [N, d]

        # 2. Compute edge messages
        msg_input = torch.cat([x_a[src], x_a[dst], edge_attr], dim=-1)  # [E, 3d]
        messages  = self.msg_mlp(msg_input)                              # [E, d]

        # 3. Aggregate messages at each destination (sum)
        agg = torch.zeros_like(x)
        agg.index_add_(0, dst, messages)                   # [N, d]

        # 4. Update nodes
        x_new = self.node_mlp(torch.cat([x_a, agg], dim=-1))  # [N, d]

        # 5. Reward from graph embedding
        graph_emb = x_new.mean(dim=0)                      # [d]
        reward    = self.reward_head(graph_emb)             # [1]

        next_graph = GraphState(x=x_new, edge_index=edge_index, edge_attr=edge_attr)
        return next_graph, reward.squeeze(-1)


class GraphPolicy(nn.Module):
    """
    Policy over a GraphState.
    Reads the graph via mean-pooling + MLP → action logits.
    """

    def __init__(self, d: int = EMBED_DIM, vocab_size: int = VOCAB_SIZE):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d, d),
            nn.LayerNorm(d),
            nn.ReLU(),
            nn.Linear(d, vocab_size),
        )

    def forward(self, graph: GraphState) -> torch.Tensor:
        """
        graph: GraphState
        Returns: [vocab_size] action logits
        """
        emb = graph.x.mean(dim=0)   # [d]  mean pool over objects
        return self.net(emb)        # [vocab_size]
