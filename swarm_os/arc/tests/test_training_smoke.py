from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import torch

ARC_ROOT = Path(__file__).resolve().parents[1]
if str(ARC_ROOT) not in sys.path:
    sys.path.insert(0, str(ARC_ROOT))

from dsl.vm import DSLVM
from model.encoder import Encoder
from model.transformer_policy import TransformerPolicy
from utils import accuracy, pad_grid


def test_real_arc_sample_policy_backward_is_gradient_safe():
    random.seed(7)
    np.random.seed(7)
    torch.manual_seed(7)

    task_path = ARC_ROOT / "data" / "arc_data" / "00576224.json"
    task = json.loads(task_path.read_text())
    example = task["train"][0]
    inp = np.array(example["input"], dtype=np.int64)
    out = np.array(example["output"], dtype=np.int64)

    encoder = Encoder(d=32)
    policy = TransformerPolicy(vocab_size=11, d=32, nhead=4, nlayers=1)
    vm = DSLVM()

    x = torch.tensor(pad_grid(inp), dtype=torch.long).unsqueeze(0)
    z = encoder(x)
    program, log_prob = policy.sample(z, max_len=3)
    prediction = vm.run(program.detach().cpu().numpy(), inp)
    observed_accuracy = accuracy(prediction, out)

    loss = -log_prob * 0.5
    loss.backward()

    grads = [p.grad for p in policy.parameters() if p.grad is not None]
    assert len(program) == 3
    assert 0.0 <= observed_accuracy <= 1.0
    assert grads
    assert all(torch.isfinite(g).all().item() for g in grads)
