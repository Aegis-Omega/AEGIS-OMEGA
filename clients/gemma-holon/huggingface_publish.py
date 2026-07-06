#!/usr/bin/env python3
"""Publish the AEGIS-Ω Gemma-4E4B holon to the Hugging Face Hub.

This holon has NO trained weights — it is a constitutional validation node
defined by config + system prompts that run on top of stock Gemma-4E4B on
device. So what we publish is a model card plus the holon's artifacts
(config, prompts, gates, the mobile control server). The card declares the
base model and the constitutional contract so the repo is honest about what
it is.

Usage:
    pip3 install huggingface_hub
    export HF_TOKEN=hf_xxx            # your write token — never commit this
    python3 huggingface_publish.py                 # dry run: lists what would upload
    python3 huggingface_publish.py --publish       # actually creates + uploads
    python3 huggingface_publish.py --publish --repo your-org/gemma-4e4b-holon

Defaults to a DRY RUN. Nothing leaves this machine unless you pass --publish.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REPO = os.environ.get("HF_REPO_ID", "aegis-omega/gemma-4e4b-holon")
BASE_MODEL = "google/gemma-3n-E4B-it"

# Files uploaded to the Hub, relative to this directory. README.md is generated.
ARTIFACTS = [
    "config.json",
    "state.json",
    "OGEMMA.md",
    "ogemma_mythos.py",
    "submit.py",
    "mythos-x-gemma.json",
    "skills/ogemma-gate.json",
    "skills/ogemma-gate.md",
    "skills/stochastic-engine.md",
    "quantum/server.py",
    "quantum/platform-helpers.py",
]

MODEL_CARD = f"""---
license: gemma
base_model: {BASE_MODEL}
tags:
  - aegis-omega
  - constitutional-ai
  - gemma
  - on-device
  - governance
library_name: transformers
pipeline_tag: text-generation
---

# AEGIS-Ω · Gemma-4E4B Holon

A **constitutional validation holon** for the AEGIS-Ω / MYTHOS pipeline. It runs
stock **[{BASE_MODEL}](https://huggingface.co/{BASE_MODEL})** on device (iPhone /
Gemma.cpp / Transformers.js) and turns it into an isolated governance node: it
receives a biological state vector and returns a constitutional verdict that is
hash-chained into the AEGIS audit fabric.

> There are **no fine-tuned weights** in this repository. The holon is defined by
> the system prompts, gates, and config published here, applied to the base
> Gemma-4E4B model. This keeps the artifact honest and replay-verifiable.

## Constitutional contract

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
φ = 0.6180339887   (1/φ quorum threshold)
```

The holon never holds hidden memory and communicates only through a mediated
verdict envelope. Every verdict is reduced to a SHA-256 chain entry on the
AEGIS Worker (`/platform/holon/validate`), so its participation is
tamper-evident.

## Verdict schema

```json
{{"verdict": "APPROVED | FAILED", "confidence": 0.94, "reason_code": "NOMINAL"}}
```

Decision rules (first match wins):

1. `stress >= 0.8`  → `FAILED` / `LIMBIC_EXHAUSTION`
2. `atp <= 0`       → `FAILED` / `ATP_DEPLETION`
3. otherwise        → `APPROVED`

## Bio-state input

| Field     | Range     | Meaning                              |
|-----------|-----------|--------------------------------------|
| stress    | 0.0–1.0   | FAILED when ≥ 0.8                    |
| attention | 0.0–1.0   | attentional engagement              |
| rir       | 0.0–1.0   | respiratory irregularity ratio      |
| atp       | 0–2500    | FAILED when ≤ 0                      |

## Three gates (MYTHOS pipeline)

| Gate             | Timing                       | Effect on FAILED       |
|------------------|------------------------------|------------------------|
| PRE_ORCHESTRATE  | before pipeline starts       | hard veto → ABORT      |
| POST_VALIDATE    | after plan approved          | soft veto → RECONCILE  |
| POST_REVIEW      | after reviewer returns PASS  | suspend gate           |

## Quorum weights

| Node                  | Weight     |
|-----------------------|------------|
| Claude (coordinator)  | 618 / 1000 |
| Gemma holon           | 191 / 1000 |
| Constitutional audit  | 191 / 1000 |
| Threshold             | ≥ 618 (= 1/φ) |

## Mathematical grounding

`λ_attn = σ₁(QKᵀ) / τ_bio` with `τ_bio = √d_k · (atp/2500) · exp(-stress_norm)`.
Collapse when `λ_attn ≥ λ_c = 1.0` (BBP phase transition). The holon detects
martingale suspension (`σ² ≥ 2β`) at the biological layer before any upstream
API call is made.

**Epistemic tier:** T2 (engineering hypothesis — computable, not yet proven optimal).

## Files

- `config.json` — holon identity, schemas, system prompt
- `OGEMMA.md` — full gate + pipeline documentation
- `skills/` — gate definitions and the stochastic engine note
- `ogemma_mythos.py` / `submit.py` — pipeline runner + chain submitter
- `quantum/server.py` — unified mobile control server + dashboard

## License

Inherits the [Gemma license](https://ai.google.dev/gemma/terms) from the base model.
"""


def collect_files() -> tuple[list[Path], list[str]]:
    present, missing = [], []
    for rel in ARTIFACTS:
        p = HERE / rel
        (present if p.is_file() else missing).append(p if p.is_file() else rel)
    return present, missing  # type: ignore[return-value]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"HF repo id (default: {DEFAULT_REPO})")
    ap.add_argument("--publish", action="store_true", help="actually create + upload (otherwise dry run)")
    ap.add_argument("--private", action="store_true", help="create the repo as private")
    args = ap.parse_args()

    present, missing = collect_files()
    if missing:
        print("Missing artifacts (will be skipped):")
        for m in missing:
            print(f"  - {m}")

    print(f"\nRepo:       {args.repo}")
    print(f"Base model: {BASE_MODEL}")
    print(f"Card:       README.md ({len(MODEL_CARD)} bytes, generated)")
    print(f"Artifacts:  {len(present)} files")
    for p in present:
        print(f"  - {p.relative_to(HERE)}")

    if not args.publish:
        print("\nDRY RUN — nothing uploaded. Re-run with --publish to push to the Hub.")
        return 0

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("\nERROR: HF_TOKEN is not set. export HF_TOKEN=hf_xxx and retry.", file=sys.stderr)
        return 2

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("\nERROR: huggingface_hub not installed. pip3 install huggingface_hub", file=sys.stderr)
        return 2

    api = HfApi(token=token)
    print(f"\nCreating repo {args.repo} (private={args.private}) ...")
    api.create_repo(repo_id=args.repo, repo_type="model", private=args.private, exist_ok=True)

    print("Uploading README.md ...")
    api.upload_file(
        path_or_fileobj=MODEL_CARD.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=args.repo,
        repo_type="model",
    )

    for p in present:
        rel = str(p.relative_to(HERE))
        print(f"Uploading {rel} ...")
        api.upload_file(
            path_or_fileobj=str(p),
            path_in_repo=rel,
            repo_id=args.repo,
            repo_type="model",
        )

    print(f"\nDone → https://huggingface.co/{args.repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
