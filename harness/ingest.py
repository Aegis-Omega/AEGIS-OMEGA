#!/usr/bin/env python3
"""Generate the AEGIS evidence-bound skill registry.

Documentation declares candidate capabilities. It never seeds operational
competence. Zero-run skills are emitted as UNOBSERVED with an authority-safe
score of zero and a content-bound registry root.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness.sdk.docs_harness import ingest
from harness.sdk.skill_authority import (
    evaluate_registry,
    render_authority_markdown,
    sanitize_legacy_tree,
)


def _git_head(repo_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("skill registry generation requires a bound git commit") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="AEGIS evidence-bound skill registry ingestion")
    parser.add_argument("repo_root", nargs="?", default=None,
                        help="Repository root (default: auto-detect from this file)")
    parser.add_argument("--source-commit", default=None,
                        help="Exact source commit; defaults to git rev-parse HEAD")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--write", action="store_true",
                              help="Write harness/skill_tree.json and .agent/skills.md")
    output_group.add_argument("--json-only", action="store_true",
                              help="Print canonical registry JSON and exit")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).parent.parent
    source_commit = args.source_commit or _git_head(repo_root)

    legacy_tree = ingest(repo_root).to_dict()
    tree = sanitize_legacy_tree(legacy_tree, source_commit=source_commit)
    receipt = evaluate_registry(tree, repo_root=repo_root)
    if receipt.outcome != "ADMITTED":
        for violation in receipt.violations:
            print(f"[ingest] DENIED: {violation}", file=sys.stderr)
        raise SystemExit(2)

    payload = json.dumps(tree, ensure_ascii=False, indent=2) + "\n"
    print(f"[ingest] repo_root      = {repo_root}", file=sys.stderr)
    print(f"[ingest] source_commit  = {source_commit}", file=sys.stderr)
    print(f"[ingest] docs found     = {tree['doc_count']}", file=sys.stderr)
    print(f"[ingest] skills         = {len(tree['skills'])}", file=sys.stderr)
    print(f"[ingest] registry_root  = {tree['registry_root']}", file=sys.stderr)
    print(f"[ingest] receipt_hash   = {receipt.receipt_hash}", file=sys.stderr)

    if args.write:
        skill_tree_path = repo_root / "harness" / "skill_tree.json"
        skills_md_path = repo_root / ".agent" / "skills.md"
        skill_tree_path.write_text(payload, encoding="utf-8")
        skills_md_path.write_text(render_authority_markdown(tree) + "\n", encoding="utf-8")
        print(f"[ingest] wrote          = {skill_tree_path}", file=sys.stderr)
        print(f"[ingest] wrote          = {skills_md_path}", file=sys.stderr)
        return

    print(payload, end="")


if __name__ == "__main__":
    main()
