"""
ARC v3 — Beam Search
Finds the highest-scoring program for a given context z.
"""

import torch
import torch.nn.functional as F
from config import MAX_PROGRAM_LEN, VOCAB_SIZE


def beam_search(
    policy,
    z: torch.Tensor,
    beam: int = 5,
    steps: int = MAX_PROGRAM_LEN,
) -> list[int]:
    """
    Beam search over programs.
    z: (1, d) context vector from encoder.
    Returns: best program as list[int] of length `steps`.
    """
    device = z.device
    # Each beam entry: (token_list, log_score)
    beams: list[tuple[list[int], float]] = [([], 0.0)]

    for t in range(steps):
        new_beams = []
        for seq, score in beams:
            # Build padded sequence tensor
            padded = seq + [0] * (steps - len(seq))
            seq_tensor = torch.tensor([padded], dtype=torch.long, device=device)

            logits = policy.forward(z, seq_tensor)          # (1, steps, V)
            log_p  = F.log_softmax(logits[0, t], dim=-1)    # (V,)

            # Top-beam expansions
            top_lp, top_ids = torch.topk(log_p, min(beam, VOCAB_SIZE))
            for lp, idx in zip(top_lp.tolist(), top_ids.tolist()):
                new_beams.append((seq + [idx], score + lp))

        # Keep top-beam beams
        beams = sorted(new_beams, key=lambda x: x[1], reverse=True)[:beam]

    return beams[0][0]  # best program
