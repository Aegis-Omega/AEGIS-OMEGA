"""
ARC v3 — Graph Beam Search
Latent planning over graph rollouts, not flat token sequences.

Each beam entry explores a sequence of DSL actions applied to the object graph
via the learned world model. The world model's reward signal guides the search.

beam_search returns the highest-scoring program (list of DSL op ints).
"""

import torch
import torch.nn.functional as F
from model.graph_state import GraphState
from config import MAX_PROGRAM_LEN, VOCAB_SIZE


def graph_beam_search(
    policy,
    world_model,
    graph: GraphState,
    beam: int = 6,
    depth: int = MAX_PROGRAM_LEN,
) -> list[int]:
    """
    policy:      GraphPolicy — outputs action logits from a GraphState
    world_model: GraphWorldModel — predicts next graph + reward
    graph:       initial GraphState (encoded input grid)
    beam:        number of beams to keep
    depth:       program length (= MAX_PROGRAM_LEN)

    Returns: best program as list[int] of length `depth`
    """
    device = graph.x.device

    # Each beam: (current_graph, program_so_far, cumulative_reward)
    beams: list[tuple[GraphState, list[int], float]] = [(graph, [], 0.0)]

    for step in range(depth):
        candidates = []

        for g, program, score in beams:
            # Get action distribution from policy
            logits = policy(g)                              # [vocab_size]
            log_p  = F.log_softmax(logits, dim=-1)

            # Expand top-beam actions
            top_lp, top_acts = torch.topk(log_p, min(beam, VOCAB_SIZE))

            for lp, act in zip(top_lp.tolist(), top_acts.tolist()):
                act_tensor = torch.tensor(act, dtype=torch.long, device=device)
                with torch.no_grad():
                    g_next, reward = world_model(g, act_tensor)

                candidates.append((
                    g_next,
                    program + [act],
                    score + lp + reward.item(),   # log_prob + learned reward
                ))

        # Keep top-beam candidates
        beams = sorted(candidates, key=lambda x: x[2], reverse=True)[:beam]

    return beams[0][1]   # best program
