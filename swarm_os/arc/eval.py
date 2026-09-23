"""
ARC v3 — Evaluation
Beam search evaluation on ARC tasks.
Reports HD_arc = 1 - accuracy. No fake values.

Run from this directory:
    python eval.py [--n 100] [--arc-data ./arc_data] [--checkpoint checkpoints/arc_v3_latest.pt]
"""

import sys
import json
import argparse
import numpy as np
import torch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from data.arc_loader import ARCLoader
from model.encoder import Encoder
from model.transformer_policy import TransformerPolicy
from model.beam_search import beam_search
from dsl.vm import DSLVM
from utils import pad_grid, accuracy
from config import DEVICE, EMBED_DIM, VOCAB_SIZE


def evaluate(args):
    device = torch.device(DEVICE)
    loader = ARCLoader(path=args.arc_data)

    enc = Encoder(d=EMBED_DIM).to(device)
    pol = TransformerPolicy(vocab_size=VOCAB_SIZE).to(device)
    vm  = DSLVM()

    if args.checkpoint and Path(args.checkpoint).exists():
        ckpt = torch.load(args.checkpoint, map_location=device)
        enc.load_state_dict(ckpt["enc"])
        pol.load_state_dict(ckpt["pol"])
        print(f"Loaded checkpoint: {args.checkpoint}")
        if "metrics" in ckpt:
            print(f"  training metrics: {ckpt['metrics']}")
    else:
        print("[WARN] No checkpoint — evaluating untrained model (baseline HD=1.0 expected)")

    enc.eval()
    pol.eval()

    scores = []
    with torch.no_grad():
        for i in range(args.n):
            t = loader.sample()
            inp_pad = torch.tensor(pad_grid(t["input"]), dtype=torch.long, device=device)
            z = enc(inp_pad.unsqueeze(0))
            prog = beam_search(pol, z, beam=args.beam)
            pred = vm.run(prog, t["input"])
            acc = accuracy(pred, t["output"])
            scores.append(acc)
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{args.n}] mean_acc={np.mean(scores):.4f}")

    mean_acc = float(np.mean(scores))
    hd_arc   = 1.0 - mean_acc
    std_acc  = float(np.std(scores))

    result = {
        "n_samples": args.n,
        "mean_acc":  round(mean_acc, 4),
        "std_acc":   round(std_acc,  4),
        "hd_arc":    round(hd_arc,   4),
        "beam":      args.beam,
    }
    print("\n=== ARC v3 EVAL RESULTS ===")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARC v3 evaluation")
    parser.add_argument("--n",          type=int,  default=100)
    parser.add_argument("--beam",       type=int,  default=5)
    parser.add_argument("--arc-data",   type=str,  default="arc_data")
    parser.add_argument("--checkpoint", type=str,  default="checkpoints/arc_v3_latest.pt")
    args = parser.parse_args()
    evaluate(args)
