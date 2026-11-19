#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
ARC = ROOT / "swarm_os" / "arc"
if str(ARC) not in sys.path:
    sys.path.insert(0, str(ARC))

import train as arc_train

SEED = 11


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True, warn_only=True)

    data = ARC / "data" / "arc_data"
    tasks = sorted(data.glob("*.json"))
    if len(tasks) != 800:
        raise SystemExit(f"expected 800 ARC tasks, found {len(tasks)}")

    checkpoint = ARC / "checkpoints" / "arc_v3_latest.pt"
    if checkpoint.exists():
        checkpoint.unlink()

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        arc_train.train(argparse.Namespace(steps=100, arc_data=str(data)))

    if not checkpoint.is_file():
        raise SystemExit("100-step smoke did not emit checkpoint")

    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise SystemExit("checkpoint metrics missing")
    if metrics.get("steps") != 100 or metrics.get("tasks_seen") != 800:
        raise SystemExit(f"unexpected checkpoint metrics: {metrics}")

    result = {
        "schema": "AEGIS_ARCHIVE_ARC_TRAINING_100_SMOKE_V1",
        "status": "PASS",
        "seed": SEED,
        "steps": 100,
        "tasks_available": 800,
        "metrics": metrics,
        "checkpoint": {
            "size_bytes": checkpoint.stat().st_size,
            "sha256": sha256_file(checkpoint),
            "committed": False,
        },
        "interpretation": "TRAINING_PATH_EXECUTION_ONLY_NOT_HELD_OUT_BENCHMARK",
        "production_wiring": "NOT_PERFORMED",
        "authority_effect": "NONE",
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
