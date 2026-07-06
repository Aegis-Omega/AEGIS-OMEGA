#!/usr/bin/env python3
"""
Emit the genomics lineage as a language-neutral fixture for cross-runtime replay.

Writes stages.json = {
  "stages":   [ {"stage": <str>, "output": <obj>}, ... ]   # ordered, GENESIS-relative
  "expected": { "terminal": <sha256hex>, "stage_hashes": [<sha256hex>, ...] }
}

Each other runtime (Node, Rust) reads ONLY the ordered stages, rebuilds the chain
from GENESIS with its OWN canonicalizer + SHA-256, and must reproduce `expected`
byte-for-byte. That is the constitution's headline property — identical topology hash
across runtimes — demonstrated on the genomics certificate.

The fixture is pure ASCII + integers (no float, canon rejects it), so NFC
normalization is the identity here and cannot cause cross-language drift.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "genomics")))
from replay_pipeline import run_pipeline, SAMPLE_REFERENCE, SAMPLE_READS  # noqa: E402

chain = run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS)
fixture = {
    "stages": [{"stage": r.stage, "output": r.output} for r in chain.records],
    "expected": {
        "terminal": chain.terminal_hash(),
        "stage_hashes": [r.stage_hash for r in chain.records],
    },
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stages.json")
with open(out, "w") as f:
    json.dump(fixture, f, indent=2, sort_keys=True)
    f.write("\n")
print(f"wrote {out}")
print(f"python terminal: {fixture['expected']['terminal']}")
