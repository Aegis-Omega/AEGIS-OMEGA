"""
ARC v3 — Grammar Policy
Generates sequences of grammar rule IDs (not primitive op ints).

As macros are added to MacroLibrary, the output head grows dynamically.
The policy learns to prefer macros when the graph trigger pattern matches —
high-level plans emerge naturally from the MDL-compressed grammar.

Architecture:
  GraphState → mean-pool → [d_model]
  + PositionalEmbedding(t)
  → TransformerDecoder (conditions on graph embedding)
  → Linear(d_model, |library|)   ← grows as macros are added
  → softmax over current rule set

Dynamic head expansion:
  When new macros are added to the library, call expand_head() to add
  new output neurons (initialized near zero so existing behavior is preserved).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from config import EMBED_DIM, MAX_PROGRAM_LEN


class GrammarPolicy(nn.Module):
    def __init__(self, library, d: int = EMBED_DIM, n_head: int = 4, n_layer: int = 2):
        super().__init__()
        self.d       = d
        self.library = library

        # Graph context projection
        self.ctx_proj = nn.Linear(d, d)

        # Positional embedding for generation steps
        self.pos_emb = nn.Parameter(torch.randn(1, MAX_PROGRAM_LEN + 1, d) * 0.02)

        # Rule embedding — one per rule in library (grows with macros)
        self._n_rules = library.vocab_size()
        self.rule_emb = nn.Embedding(self._n_rules, d)

        # Causal transformer decoder
        layer = nn.TransformerEncoderLayer(
            d_model=d, nhead=n_head, dim_feedforward=d * 4,
            dropout=0.1, batch_first=True, norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(layer, n_layer)

        # Output head — maps to rule logits (size grows dynamically)
        self.head = nn.Linear(d, self._n_rules)

    # ── Dynamic head expansion ─────────────────────────────────────────────

    def expand_head(self) -> int:
        """
        Expand output head and rule embeddings when new macros are added.
        Returns number of new rules added.
        """
        new_size = self.library.vocab_size()
        if new_size == self._n_rules:
            return 0
        added = new_size - self._n_rules

        # Expand rule embeddings
        old_emb = self.rule_emb.weight.data
        new_emb = torch.randn(added, self.d) * 0.01
        self.rule_emb = nn.Embedding(new_size, self.d)
        self.rule_emb.weight.data = torch.cat([old_emb, new_emb], dim=0)

        # Expand output head
        old_w = self.head.weight.data
        old_b = self.head.bias.data
        new_w = torch.zeros(added, self.d)
        new_b = torch.full((added,), -2.0)   # start near zero probability
        self.head = nn.Linear(self.d, new_size)
        self.head.weight.data = torch.cat([old_w, new_w], dim=0)
        self.head.bias.data   = torch.cat([old_b, new_b], dim=0)

        self._n_rules = new_size
        return added

    # ── Forward ───────────────────────────────────────────────────────────────

    def _causal_mask(self, T: int, device) -> torch.Tensor:
        return torch.triu(torch.ones(T, T, device=device), diagonal=1).bool()

    def forward(self, graph_state, seq: torch.Tensor) -> torch.Tensor:
        """
        graph_state: GraphState
        seq:         [1, T] LongTensor of rule indices
        Returns:     [1, T, n_rules] logits
        """
        T      = seq.shape[1]
        ctx    = self.ctx_proj(graph_state.x.mean(0, keepdim=True))   # [1, d]
        ctx    = ctx.unsqueeze(1) + self.pos_emb[:, :1]               # [1, 1, d]
        tok    = self.rule_emb(seq) + self.pos_emb[:, 1:T+1]          # [1, T, d]
        x      = torch.cat([ctx, tok], dim=1)                         # [1, T+1, d]
        mask   = self._causal_mask(T + 1, seq.device)
        h      = self.transformer(x, mask=mask)                       # [1, T+1, d]
        return self.head(h[:, 1:])                                     # [1, T, n_rules]

    def sample(self, graph_state, max_len: int = MAX_PROGRAM_LEN):
        """
        Sample a grammar program autoregressively.
        Returns: (rule_indices: LongTensor[max_len], log_prob: Tensor)
        """
        device = graph_state.x.device
        seq    = torch.zeros((1, max_len), dtype=torch.long, device=device)
        lps    = []

        for t in range(max_len):
            logits = self.forward(graph_state, seq[:, :t+1])   # [1,t+1,n]
            probs  = F.softmax(logits[0, -1], dim=-1)
            dist   = torch.distributions.Categorical(probs)
            tok    = dist.sample()
            seq[0, t] = tok
            lps.append(dist.log_prob(tok))

        return seq[0], torch.stack(lps).sum()
