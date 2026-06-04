#!/usr/bin/env python3
"""
harness/ingest.py — Docs Harness runner

Usage:
    python harness/ingest.py                    # auto-detect repo root
    python harness/ingest.py /path/to/repo      # explicit root
    python harness/ingest.py --write            # write skill_tree.json + skills.md

Outputs:
    harness/skill_tree.json    — machine-readable Phase 1 skill tree
    .agent/skills.md           — human-readable skills registry (--write only)
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from harness.sdk.docs_harness import ingest, render_skills_md


def main() -> None:
    parser = argparse.ArgumentParser(description="AEGIS Docs Harness — Phase 1 skill tree ingestion")
    parser.add_argument("repo_root", nargs="?", default=None,
                        help="Repository root (default: auto-detect from this file's location)")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--write", action="store_true",
                              help="Write skill_tree.json and .agent/skills.md")
    output_group.add_argument("--json-only", action="store_true",
                              help="Print JSON to stdout and exit")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).parent.parent

    print(f"[ingest] repo_root  = {repo_root}", file=sys.stderr)
    print(f"[ingest] phase      = 1 (static, human-authored baseline)", file=sys.stderr)

    tree = ingest(repo_root)

    print(f"[ingest] docs found = {tree.doc_count}", file=sys.stderr)
    print(f"[ingest] skills     = {len(tree.skills)}", file=sys.stderr)

    if args.json_only:
        print(tree.to_json())
        return

    if args.write:
        skill_tree_path = repo_root / "harness" / "skill_tree.json"
        skills_md_path  = repo_root / ".agent" / "skills.md"

        skill_tree_path.write_text(tree.to_json(), encoding="utf-8")
        skills_md_path.write_text(render_skills_md(tree), encoding="utf-8")

        print(f"[ingest] wrote  → {skill_tree_path}", file=sys.stderr)
        print(f"[ingest] wrote  → {skills_md_path}", file=sys.stderr)
    else:
        # Default: print JSON to stdout
        print(tree.to_json())


if __name__ == "__main__":
    main()
