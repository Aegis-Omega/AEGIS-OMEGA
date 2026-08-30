#!/usr/bin/env python3
"""MUSTALAH-ANANA-REPLAY-001 — deterministic sample selection (amendment §11).

Given the frozen spec hash and the full eligible case frame, applies:
    N < 30          -> FEASIBILITY_FAILURE
    30 <= N <= 100  -> full census
    N > 100         -> 100 cases with smallest SHA256(spec_hash || case_id)

Usage:
    python3 sample_select.py <spec_hash> <case_ids.txt>

case_ids.txt: one case_id per line, UTF-8. Output: selected case_ids on
stdout in hash rank order, verdict line on stderr. Exit 2 on feasibility
failure so the ledger records it as a result, not an error to retry.
"""
import hashlib
import sys


def rank(spec_hash: str, case_id: str) -> str:
    return hashlib.sha256((spec_hash + case_id).encode("utf-8")).hexdigest()


def select(spec_hash: str, case_ids: list[str]) -> tuple[str, list[str]]:
    n = len(case_ids)
    if n < 30:
        return "FEASIBILITY_FAILURE", []
    if n <= 100:
        return "FULL_CENSUS", sorted(case_ids)
    ranked = sorted(case_ids, key=lambda c: rank(spec_hash, c))
    return "DETERMINISTIC_100", ranked[:100]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    spec_hash = sys.argv[1]
    with open(sys.argv[2], encoding="utf-8") as f:
        ids = [line.strip() for line in f if line.strip()]
    if len(ids) != len(set(ids)):
        print("duplicate case_ids in frame", file=sys.stderr)
        sys.exit(1)
    verdict, chosen = select(spec_hash, ids)
    print(f"N={len(ids)} verdict={verdict} selected={len(chosen)}", file=sys.stderr)
    if verdict == "FEASIBILITY_FAILURE":
        sys.exit(2)
    for c in chosen:
        print(c)
