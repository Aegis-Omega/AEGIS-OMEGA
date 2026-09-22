"""
ARC v3 — Graph World Model Training Loop
PPO + CVS + MDL over object-graph states.

Architecture:
  GridToGraph  → extract objects + spatial edges (no learned params)
  GraphEncoder → lift raw features to d_model embeddings
  GraphPolicy  → action logits from mean-pooled graph embedding
  GraphWorldModel → latent graph transition + reward
  GraphBeamSearch → latent planning over graph rollouts at eval time

The key difference from train.py:
  - State is G=(V,E), not a flat padded grid
  - World model learns F: G × A → G', reward
  - Beam search plans in graph space, not token sequence space
  - Object identity persists across transitions — no semantic collapse

Usage:
    python train_graph.py [--steps 10000] [--arc-data ./arc_data]
"""

import os
import sys
import json
import argparse
import time
import numpy as np
import torch
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from data.arc_loader import ARCLoader
from model.graph_encoder import GraphEncoder
from model.graph_world_model import GraphWorldModel, GraphPolicy
from model.value import Value
from dsl.vm import DSLVM
from memory.replay import ReplayBuffer
from curriculum.curriculum import Curriculum
from selfplay.mutate import perturbations
from utils import accuracy, compute_cvs, compute_mdl
from config import (
    DEVICE, EMBED_DIM, VOCAB_SIZE, MAX_PROGRAM_LEN,
    LR, BATCH_SIZE, CVS_WEIGHT, MDL_WEIGHT, STATE_PATH
)


def atomic_write_state(state_path: Path, arc_metrics: dict) -> None:
    if not state_path.exists():
        return
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["arc_benchmark"] = {
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "model": "graph_world_model_v3",
            **arc_metrics,
        }
        state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, state_path)
    except Exception as e:
        print(f"[WARN] state.json update failed: {e}")


def sample_program_graph(policy, world_model, graph, max_len: int = MAX_PROGRAM_LEN):
    """
    Sample a program by rolling out the world model step-by-step.
    Returns: (program list[int], total_log_prob Tensor, total_reward Tensor)
    """
    program    = []
    log_probs  = []
    rewards    = []
    g = graph

    for _ in range(max_len):
        logits = policy(g)
        dist   = torch.distributions.Categorical(logits=logits)
        action = dist.sample()
        log_probs.append(dist.log_prob(action))

        g, reward = world_model(g, action)
        rewards.append(reward)
        program.append(action.item())

    return program, torch.stack(log_probs).sum(), torch.stack(rewards).sum()


def train(args):
    device = torch.device(DEVICE)

    loader  = ARCLoader(path=args.arc_data)
    print(f"Loaded {len(loader)} ARC tasks from '{args.arc_data}'")

    enc = GraphEncoder(d=EMBED_DIM).to(device)
    pol = GraphPolicy(d=EMBED_DIM, vocab_size=VOCAB_SIZE).to(device)
    wm  = GraphWorldModel(d=EMBED_DIM).to(device)
    val = Value(d=EMBED_DIM).to(device)
    vm  = DSLVM()
    buf = ReplayBuffer()
    cur = Curriculum()

    opt_pw = torch.optim.Adam(
        list(enc.parameters()) + list(pol.parameters()) + list(wm.parameters()), lr=LR
    )
    opt_v = torch.optim.Adam(val.parameters(), lr=LR)

    best_acc   = 0.0
    acc_history = []
    cvs_history = []
    t0 = time.time()

    for step in range(1, args.steps + 1):
        task = cur.apply(loader.sample())

        # Encode input grid as object graph
        graph = enc(task["input"], device=device)

        # Sample program via world model rollout
        prog_list, logp, wm_reward = sample_program_graph(pol, wm, graph, MAX_PROGRAM_LEN)
        prog_np = np.array(prog_list, dtype=np.int64)

        # Execute on real grid (ground truth)
        pred = vm.run(prog_np, task["input"])
        acc  = accuracy(pred, task["output"])

        # CVS: program stability under input perturbations
        perturbed_tasks = perturbations(task, n=3)
        perturbed_outs  = [vm.run(prog_np, pt["input"]) for pt in perturbed_tasks]
        cvs = compute_cvs(perturbed_outs)

        # MDL: effective program length
        mdl = compute_mdl(prog_np)

        # Final reward (ground truth + world model reward as auxiliary)
        reward = acc + CVS_WEIGHT * cvs - MDL_WEIGHT * mdl

        # PPO: advantage = real_reward - value_estimate
        graph_emb = graph.x.mean(dim=0, keepdim=True)   # [1, d]
        v_est     = val(graph_emb).squeeze()
        adv       = reward - v_est.item()

        loss_p = -(logp + wm_reward * 0.1) * adv   # wm_reward as auxiliary signal
        loss_v = (v_est - reward) ** 2

        opt_pw.zero_grad()
        loss_p.backward()
        torch.nn.utils.clip_grad_norm_(
            list(enc.parameters()) + list(pol.parameters()) + list(wm.parameters()), 1.0
        )
        opt_pw.step()

        opt_v.zero_grad()
        loss_v.backward()
        opt_v.step()

        acc_history.append(acc)
        cvs_history.append(cvs)
        best_acc = max(best_acc, acc)
        cur.update(acc)

        if step % 100 == 0:
            mean_acc = np.mean(acc_history[-100:])
            mean_cvs = np.mean(cvs_history[-100:])
            hd_arc   = 1.0 - mean_acc
            elapsed  = time.time() - t0
            print(
                f"step={step:6d}  acc={mean_acc:.4f}  CVS={mean_cvs:.4f}"
                f"  HD_arc={hd_arc:.4f}  nodes_avg={graph.num_nodes}  level={cur.level}"
                f"  t={elapsed:.0f}s"
            )

    mean_acc = float(np.mean(acc_history[-500:]) if acc_history else 0.0)
    mean_cvs = float(np.mean(cvs_history[-500:]) if cvs_history else 0.0)
    hd_arc   = 1.0 - mean_acc

    metrics = {
        "steps":             args.steps,
        "mean_acc":          round(mean_acc,  4),
        "mean_cvs":          round(mean_cvs,  4),
        "hd_arc":            round(hd_arc,    4),
        "best_acc":          round(best_acc,  4),
        "curriculum_level":  cur.level,
        "architecture":      "graph_world_model",
    }
    print("\n=== ARC v3 GRAPH WORLD MODEL — TRAINING COMPLETE ===")
    print(json.dumps(metrics, indent=2))

    state_path = Path(__file__).parent / STATE_PATH
    atomic_write_state(state_path, metrics)
    print(f"HD_arc={hd_arc:.4f} written to OS state.")

    ckpt_dir = Path(__file__).parent / "checkpoints"
    ckpt_dir.mkdir(exist_ok=True)
    torch.save({
        "enc": enc.state_dict(),
        "pol": pol.state_dict(),
        "wm":  wm.state_dict(),
        "val": val.state_dict(),
        "metrics": metrics,
    }, ckpt_dir / "arc_v3_graph_latest.pt")
    print(f"Checkpoint saved: {ckpt_dir / 'arc_v3_graph_latest.pt'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARC v3 Graph World Model training")
    parser.add_argument("--steps",    type=int, default=10000)
    parser.add_argument("--arc-data", type=str, default="arc_data")
    args = parser.parse_args()
    train(args)
