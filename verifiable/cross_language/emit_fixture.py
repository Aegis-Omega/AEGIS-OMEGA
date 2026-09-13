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

The stage fixture uses ASCII and small integers. Additional canonical vectors
exercise exact Unicode and code-point key ordering under aegis-integer-json-v2.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "genomics")))
from replay_pipeline import CANONICAL_PROFILE, canon, sha256_hex, run_pipeline, SAMPLE_REFERENCE, SAMPLE_READS  # noqa: E402

chain = run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS)
fixture = {
    "canonicalization": CANONICAL_PROFILE,
    "stages": [{"stage": r.stage, "output": r.output} for r in chain.records],
    "canonical_vectors": [
        {"value": value, "sha256": sha256_hex(canon(value))}
        for value in [
            {"text": "é"}, {"text": "e\u0301"},
            {"\ue000": "BMP", "\U0001f600": "non-BMP", "controls": "\b\t\n\f\r\u0000"},
            {"integers": [-9007199254740991, 0, 9007199254740991], "flags": [True, False, None]},
        ]
    ],
    "expected": {
        "terminal": chain.terminal_hash(),
        "stage_hashes": [r.stage_hash for r in chain.records],
    },
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stages.json")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    json.dump(fixture, f, indent=2, sort_keys=True)
    f.write("\n")
print(f"wrote {out}")
print(f"python terminal: {fixture['expected']['terminal']}")
