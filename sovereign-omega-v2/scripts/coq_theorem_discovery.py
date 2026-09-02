#!/usr/bin/env python3
"""Print the theorem names of one Coq source, one per line.

Single discovery routine for the attestation lane.  The compile step (inside
the opam container) and the receipt builder must agree on which theorems
exist, so both use THEOREM_RE and strip_coq_comments from
python/coq_attestation.py: a name on the line after its keyword is found by
both, a theorem inside a comment by neither.

When the compiler's own .glob file sits next to the source (it does after
coqc has run), its `prf` records are the compiler's witness.  Any difference
between the witness and the regex is refused, with both sides named, rather
than resolved by guessing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from coq_attestation import THEOREM_RE, strip_coq_comments  # noqa: E402


def regex_theorems(path: Path) -> list[str]:
    return THEOREM_RE.findall(strip_coq_comments(path.read_text(encoding="utf-8")))


def glob_proofs(glob_path: Path) -> list[str]:
    """Names of `prf` records: every Theorem/Lemma/... closed by Qed."""
    names = []
    for line in glob_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "prf":
            names.append(parts[3])
    return names


def discover_theorems(path: Path) -> list[str]:
    names = regex_theorems(path)
    glob_path = path.with_suffix(".glob")
    if glob_path.exists():
        witness = glob_proofs(glob_path)
        if sorted(names) != sorted(witness):
            only_regex = sorted(set(names) - set(witness))
            only_glob = sorted(set(witness) - set(names))
            raise SystemExit(
                f"{path}: theorem discovery disagrees with the compiler's .glob "
                f"witness; source-only={only_regex} glob-only={only_glob}"
            )
    return names


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: coq_theorem_discovery.py <file.v>")
    for name in discover_theorems(Path(sys.argv[1])):
        print(name)
