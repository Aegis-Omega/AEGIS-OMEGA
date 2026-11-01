#!/usr/bin/env python3
"""Exact-source atomic patch for AEGIS chain.mjs lock ownership defect.

Default: dry-run. Apply only on approved existing branch and after exact-head review.
The invariant is: failure to acquire the lock must not proceed or release another
writer's lock. This changes a two-way race to an explicit fail-closed exception.
"""
from __future__ import annotations
import argparse
from pathlib import Path

OLD = '  return false // stale lock — proceed anyway rather than deadlock'
NEW = "  throw new Error('metacog: lock acquisition failed; concurrent writer; no mutation')"

def repair(source: str) -> str:
    if source.count(OLD) != 1:
        raise ValueError('expected lock fallback not present exactly once; refuse speculative patch')
    if '  acquireLock()\n  try {' not in source:
        raise ValueError('expected observe() lock boundary missing')
    return source.replace(OLD, NEW)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='existing .claude/metacog/chain.mjs')
    ap.add_argument('--apply', action='store_true', help='replace in-place after explicit operator-authorized gate')
    a = ap.parse_args()
    p=Path(a.path)
    original=p.read_text(encoding='utf-8')
    updated=repair(original)
    if a.apply:
        p.write_text(updated,encoding='utf-8')
        print('PATCHED_AND_NEEDS_NATIVE_TEST')
    else:
        print('MATCHED_DRY_RUN_NO_MUTATION')
