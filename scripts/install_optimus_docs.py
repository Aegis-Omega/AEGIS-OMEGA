#!/usr/bin/env python3
"""Safely reconcile existing AEGIS docs without destroying historical material.

Default: preview diff ONLY. --apply requires clean checkout and exact expected HEAD.
Never edits `.claude.json`, protected configuration, code, workflows, or secrets.
"""
from __future__ import annotations
import argparse
import difflib
from pathlib import Path
import subprocess
import sys

MARKER = '<!-- AEGIS_OPTIMUS_EVOLUTION_DOC_BOUNDARY_V1 -->'
PANELS = {
  "REPO_MAP.md": """# AEGIS Ω | Canonical repository map entry point

**Current-source rule:** this file contains historical observations; run `python3 scripts/aegis_topology.py --repo . --summary` on the exact current commit for the actual folder census. `docs/architecture/OPTIMUS_EVOLUTION.md` defines ownership and migration gates. Source presence is not live deployment, test success, revenue or admission.

**2026-11-06 reconciliation:** `hub/src/components/PricingPage.tsx` and `supabase/functions/verify-paypal/index.ts` in inspected `main@c6f4f2131ab06c5b20cfd3d0eafd99e3ca246bc8` specify $49/$499 (not historical $48/$498). `agents/` is a mixed-function directory, not globally dormant. Tactical Vercel config and `infrastructure/production.json` live in unmerged candidate branches, not automatically in main.

## Navigate the architecture

- `docs/architecture/OPTIMUS_EVOLUTION.md`: logical ownership, evidence boundaries and migration constraints.
- `scripts/aegis_topology.py`: deterministic exact-HEAD folder map, unknown roots and critical missing files.
- `harness/sdk/repository_knowledge.py`: existing source-bound repository cartographer, preserved.
- `docs/archive/REPO_MAP_2026-07.md`: entire previous map, including historical deployment and pricing assertions, unchanged.

## Deployment classes

`SOURCE_PRESENT` only establishes a path exists. Never conflate it with `CI_PASS`, `DEPLOYED`, `AUTHORIZED`, `COMMERCIAL_VERIFIED`, or `OPENAI_QUALIFIED`. Confirm each property independently from exact-source receipts. Repo presence is not a functional integration.
""",
  "ASSETS.md": """# Evidence freshness boundary

The inventory below is a **historical asset register**, not proof that live services, purchases, credentials or integrations still work. Inspect `REPO_MAP.md`, `docs/architecture/OPTIMUS_EVOLUTION.md`, and provider-native receipts at the exact head. Prices in older snapshots ($48/$498) are superseded by code inspection ($49/$499) for main@c6f4f213; live checkout still requires verification.
""",
  "HANDOFF.md": """# Handoff chronology notice

This handoff is historical (sections from June/July 2026). It is not the live 2026-11 operating state. Read `REPO_MAP.md` and `docs/architecture/OPTIMUS_EVOLUTION.md`; bind any action to current exact HEAD and native receipts. The embedded access/credential instructions are historical, not present authorization for secret retrieval or deployment.
""",
  "docs/PROOF.md": """# Proof metrics freshness notice

Numbers below were collected in June/July 2026 and are **historical metrics**, not a current CI success count, formal-kernel guarantee, or deployment receipt. `#[test]` / `it()` / `def test_*` counts enumerate test definitions, not executed passes. Re-run the documented commands against an exact commit and separately inspect native CI. Source topology: `scripts/aegis_topology.py`.
""",
  "reports/repositories.md": """# Repository report freshness notice

This is a historical report. Do not treat branch counts, test counts, root-file totals or connectivity from its historical timestamp as current. Use `scripts/aegis_topology.py` (exact Git tree), then compare against actual provider records. See `docs/architecture/OPTIMUS_EVOLUTION.md`.
""",
}


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, text=True)
    return proc.stdout.strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--apply", action="store_true")
    p.add_argument("--expected-head", help="required exact 40-hex SHA with --apply")
    opts = p.parse_args()
    repo = opts.repo.resolve()
    try:
        head = git(repo, "rev-parse", "HEAD")
        if opts.apply:
            if not opts.expected_head or len(opts.expected_head) != 40 or head != opts.expected_head:
                raise ValueError("REFUSE: exact --expected-head must match current HEAD")
            if git(repo, "status", "--porcelain"):
                raise ValueError("REFUSE: worktree has staged, unstaged or untracked changes")
        updates = []
        archive = repo / "docs/archive/REPO_MAP_2026-07.md"
        for path, heading in PANELS.items():
            full = repo / path
            if not full.is_file():
                continue  # do not create a substitute document under a missing path
            previous = full.read_text(encoding="utf-8")
            if MARKER in previous:
                continue  # idempotent, preserving existing material
            if path == "REPO_MAP.md":
                if archive.exists():
                    raise ValueError("REFUSE: history archive already exists; inspect manually")
                updated = MARKER + "\n" + heading.rstrip() + "\n"
                updates.append((archive, "", previous))  # byte-preserving historical relocation
            else:
                updated = MARKER + "\n" + heading.rstrip() + "\n\n---\n\n" + previous
            updates.append((full, previous, updated))
        if not updates:
            print("NO_CHANGE: boundaries already installed or original files missing")
            return 0
        if not opts.apply:
            for path, old, new in updates:
                print("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                    fromfile=str(path.relative_to(repo)), tofile=str(path.relative_to(repo)))))
            print(f"PREVIEW_ONLY: {len(updates)} documents. No repository files changed.")
        else:
            for path, _, updated in updates:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(updated, encoding="utf-8")
            print(f"UPDATED: {len(updates)} docs at parent HEAD {head}; commit/CI NOT performed")
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
