"""
ARC v3 — Transformer Policy
Autoregressive program generator conditioned on the grid encoding z.
z is injected as a learned prefix token (cross-attention via prepend).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from config import VOCAB_SIZE, EMBED_DIM, N_HEAD, N_LAYER, MAX_PROGRAM_LEN


class TransformerPolicy(nn.Module):
    def __init__(
        self,
        vocab_size: int = VOCAB_SIZE,
        d: int = EMBED_DIM,
        nhead: int = N_HEAD,
        nlayers: int = N_LAYER,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d = d
        self.max_len = MAX_PROGRAM_LEN

        # Token + positional embeddings
        self.token_emb = nn.Embedding(vocab_size, d)
        self.pos_emb   = nn.Parameter(torch.randn(1, MAX_PROGRAM_LEN + 1, d) * 0.02)

        # Project z into token space (context prefix)
        self.z_proj = nn.Linear(d, d)

        # Causal transformer
        layer = nn.TransformerEncoderLayer(
            d_model=d, nhead=nhead, dim_feedforward=d * 4,
            dropout=0.1, batch_first=True, norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(layer, nlayers)
        self.fc = nn.Linear(d, vocab_size)

    def _causal_mask(self, T: int, device) -> torch.Tensor:
        """Upper-triangular mask for causal attention."""
        mask = torch.triu(torch.ones(T, T, device=device), diagonal=1).bool()
        return mask

    def forward(self, z: torch.Tensor, seq: torch.Tensor) -> torch.Tensor:
        """
        z:   (B, d) context from encoder
        seq: (B, T) token ids (0-padded)
        returns: (B, T, vocab_size) logits
        """
        B, T = seq.shape

        # Token embeddings + positional
        tok = self.token_emb(seq)               # (B, T, d)
        tok = tok + self.pos_emb[:, 1:T+1]      # skip pos 0 (reserved for z)

        # Prepend z as a conditioning prefix token
        z_tok = self.z_proj(z).unsqueeze(1)     # (B, 1, d)
        z_tok = z_tok + self.pos_emb[:, :1]

        x = torch.cat([z_tok, tok], dim=1)      # (B, T+1, d)
        mask = self._causal_mask(T + 1, z.device)

        h = self.transformer(x, mask=mask)      # (B, T+1, d)
        h = h[:, 1:]                            # drop z prefix → (B, T, d)
        return self.fc(h)                       # (B, T, vocab_size)

    def sample(self, z: torch.Tensor, max_len: int = MAX_PROGRAM_LEN):
        """
        Sample a program autoregressively given context z.
        Returns: (program: LongTensor[max_len], log_prob: scalar Tensor)
        """
        device = z.device
        seq = torch.zeros((1, max_len), dtype=torch.long, device=device)
        log_probs = []

        for t in range(max_len):
            logits = self.forward(z, seq[:, :t + 1])    # (1, t+1, V)
            probs  = F.softmax(logits[:, -1], dim=-1)   # (1, V)
            dist   = torch.distributions.Categorical(probs)
            token  = dist.sample()                      # (1,)
            seq[0, t] = token
            log_probs.append(dist.log_prob(token))

        return seq[0], torch.stack(log_probs).sum()
