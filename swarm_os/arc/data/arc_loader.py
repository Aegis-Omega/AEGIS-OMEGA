"""
ARC v3 — Task Loader
Loads ARC tasks from JSON files. Each task has train/test pairs.
"""

import json
import random
import numpy as np
from pathlib import Path


class ARCLoader:
    def __init__(self, path="arc_data"):
        self.path = Path(path)
        self.files = list(self.path.glob("*.json"))
        if not self.files:
            raise FileNotFoundError(
                f"No ARC task files found at '{path}'. "
                "Download ARC-AGI data and place .json files there."
            )

    def __len__(self):
        return len(self.files)

    def sample(self) -> dict:
        """Return a random train example from a random task."""
        f = random.choice(self.files)
        with open(f) as fp:
            data = json.load(fp)
        ex = random.choice(data["train"])
        return {
            "input":  np.array(ex["input"],  dtype=np.int64),
            "output": np.array(ex["output"], dtype=np.int64),
            "task":   f.stem,
        }

    def sample_task(self) -> dict:
        """Return full task (all train + test pairs) for evaluation."""
        f = random.choice(self.files)
        with open(f) as fp:
            data = json.load(fp)
        return {
            "train": [
                {"input":  np.array(p["input"],  dtype=np.int64),
                 "output": np.array(p["output"], dtype=np.int64)}
                for p in data["train"]
            ],
            "test": [
                {"input":  np.array(p["input"],  dtype=np.int64),
                 "output": np.array(p.get("output", p["input"]), dtype=np.int64)}
                for p in data.get("test", [])
            ],
            "task": f.stem,
        }
