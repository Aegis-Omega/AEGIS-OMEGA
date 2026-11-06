#!/usr/bin/env python3
"""AEGIS Ω: source-bound, read-only repository topology (stdlib only).

This does not establish live deployments, revenue, model quality or admission.
No writes, shell execution from repo, network, credentials or branch mutation.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

SCHEMA = "aegis.topology.v1"
# Logical ownership only. Existing physical paths remain unchanged.
OWNERS = {
    "sovereign-omega-v2": "runtime", "aegis-cl-psi": "runtime", "aegis-runtime": "runtime",
    "agents": "runtime", "harness": "runtime", "vertex": "runtime", "src": "runtime",
    "core": "runtime", "backend": "runtime", "crates": "runtime", "kernel-one": "runtime",
    "hub": "apps", "tactical": "apps", "cockpit": "apps", "studio": "apps",
    "platform-picker": "apps", "hook-generator": "apps", "content-calendar": "apps",
    "enterprise": "apps", "aegisomega-webgpu": "apps",
    "packages": "packages", "clients": "packages", "aegis-ccil-verifier": "packages", "schemas": "packages",
    "supabase": "integrations", "worker-src": "integrations", "terraform": "infrastructure",
    "genomics": "research", "verifiable": "research", "sovereign-mesh": "research",
    "paperclip": "research", "alignment": "research", "security": "security",
    "docs": "documentation", "reports": "evidence", ".aegis": "evidence", "scripts": "tooling",
    ".github": "automation", ".claude": "automation", ".agent": "automation",
    ".devcontainer": "tooling", ".vscode": "tooling", ".sovereign_context": "documentation",
}
# Existing paths: missing anchor is a source-tree error, not deployment failure.
ANCHORS = {
    "runtime": ["sovereign-omega-v2/python/bridge.py", "agents/coordinator.py", "harness/sdk/repository_knowledge.py"],
    "apps": ["hub/src/App.tsx", "tactical/src/App.tsx"],
    "packages": ["packages/shared/lib/access.ts"],
    "research": ["verifiable/chain.py"],
    "automation": [".github/workflows/repository-knowledge.yml"],
    "documentation": ["REPO_MAP.md", "README.md", "docs/PROOF.md"],
}
HISTORICAL_METADATA = {"reports/inventory.json": "generated_from", "docs/PROOF.md": None,
                       "HANDOFF.md": None, "ASSETS.md": None}


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=repo, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout.decode("utf-8", errors="strict").strip()


def git_paths(repo: Path) -> list[str]:
    # HEAD tree instead of working copy; rejected path with invalid Unicode.
    raw = subprocess.run(["git", "ls-tree", "-r", "--name-only", "-z", "HEAD"], cwd=repo,
                         check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    paths = [s.decode("utf-8", errors="strict") for s in raw.split(b"\x00") if s]
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate Git paths")
    return sorted(paths)


def audit(repo: Path) -> dict:
    repo = repo.resolve()
    head, tree = git(repo, "rev-parse", "HEAD"), git(repo, "rev-parse", "HEAD^{tree}")
    paths = git_paths(repo)
    pathset = set(paths)
    roots: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        pp = PurePosixPath(p)
        root = pp.parts[0] if len(pp.parts) > 1 else "[root-files]"
        roots[root].append(p)
    records = []
    for root in sorted(roots):
        files = roots[root]
        records.append({"root": root, "logical_owner": OWNERS.get(root, "unclassified"),
                        "tracked_files": len(files), "extensions": dict(sorted(Counter(
                        PurePosixPath(f).suffix or "[no-ext]" for f in files).items()))})
    checks = [{"path": p, "component": owner, "exists_at_head": p in pathset}
              for owner, group in sorted(ANCHORS.items()) for p in group]
    historical = []
    for p, key in HISTORICAL_METADATA.items():
        if p not in pathset:
            continue
        obj = {"path": p, "present": True, "head_freshness": "NOT_ESTABLISHED"}
        if key:
            try:
                # Reads committed content from the exact tree, not dirty working tree.
                metadata = json.loads(git(repo, "show", "HEAD:" + p))
                claimed = metadata.get(key)
                obj.update({"declared_commit": claimed, "matches_head": claimed == head,
                            "head_freshness": "MATCHES_HEAD" if claimed == head else "HISTORICAL"})
            except (ValueError, subprocess.CalledProcessError):
                obj["head_freshness"] = "UNPARSEABLE"
        historical.append(obj)
    root_names = {r["root"] for r in records}
    observed = {r for r in root_names if r != "[root-files]"}
    errors = ["MISSING_ANCHOR:" + c["path"] for c in checks if not c["exists_at_head"]]
    unknown = sorted(observed - OWNERS.keys())
    status = "FAILED" if errors else ("REVIEW_REQUIRED" if unknown else "PASS")
    data = {"schema": SCHEMA, "repository_root": ".", "head": head,
            "tree": tree, "tracked_files": len(paths), "status": status,
            "roots": records, "anchors": checks, "unclassified_roots": unknown,
            "historical_docs": historical, "errors": errors,
            "important_boundary": "source tree evidence, NOT deployment / CI / tests / security / revenue"}
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    data["snapshot_sha256"] = hashlib.sha256(canonical).hexdigest()
    return data



def render_markdown(audit_result: dict) -> str:
    """Human-readable projection of this exact Git-tree receipt, never independent evidence."""
    def esc(value: object) -> str:
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")

    data = audit_result
    lines = [
        "# AEGIS Ω | Source-bound folder inventory",
        "",
        f"**HEAD:** \`{data['head']}\`  ",
        f"**TREE:** \`{data['tree']}\`  ",
        f"**Status:** {data['status']}  ",
        f"**Tracked files:** {data['tracked_files']}; **root records:** {len(data['roots'])}",
        "",
        "> Logical owners classify source locations. They do not certify deployment,",
        "> import connectivity, tests, commerce, security, or agent authority.",
        "",
        "| Git root | Logical owner | Tracked files |",
        "|---|---|---:|",
    ]
    for record in data["roots"]:
        lines.append(
            f"| \`{esc(record['root'])}\` | {esc(record['logical_owner'])} | {record['tracked_files']} |"
        )
    if data["unclassified_roots"]:
        lines.extend(["", "**REVIEW_REQUIRED:** " + ", ".join(data["unclassified_roots"])])
    if data["errors"]:
        lines.extend(["", "**MISSING SOURCE ANCHORS:** " + ", ".join(data["errors"])])
    if data["historical_docs"]:
        lines.extend(["", "## Document freshness (not runtime state)", ""])
        for item in sorted(data["historical_docs"], key=lambda x: x["path"]):
            lines.append(f"- \`{esc(item['path'])}\`: {esc(item['head_freshness'])}")
    lines.extend(["", "Generated from immutable Git HEAD; do not commit as an evergreen current-state claim.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--strict", action="store_true", help="fail on missing anchors OR new unknown roots")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--summary", action="store_true", help="print brief human-readable outcome")
    mode.add_argument("--markdown", action="store_true", help="render every Git root as source-pinned Markdown")
    a = parser.parse_args()
    try:
        result = audit(a.repo)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("TOPOLOGY_UNAVAILABLE: " + str(exc), file=sys.stderr)
        return 2
    if a.markdown:
        print(render_markdown(result), end="")
    elif a.summary:
        print(f"{result['status']} head={result['head']} tree={result['tree']} "
              f"files={result['tracked_files']} roots={len(result['roots'])}")
        for err in result["errors"]:
            print(err)
        if result["unclassified_roots"]:
            print("REVIEW_NEW_ROOTS: " + ", ".join(result["unclassified_roots"]))
        for item in result["historical_docs"]:
            print(f"DOC {item['path']}: {item['head_freshness']}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 1 if result["errors"] or (a.strict and result["unclassified_roots"]) else 0

if __name__ == "__main__":
    raise SystemExit(main())
