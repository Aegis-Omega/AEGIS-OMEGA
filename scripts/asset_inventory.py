#!/usr/bin/env python3
"""Advisory, offline AEGIS estate census at a pinned local Git HEAD.

The result proves Git-tree membership only. It does NOT execute/read external
connectors, prove deployed capabilities, prove that an agent reused an asset,
or establish superiority. No network, shell, file writes, or elevated authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

SCHEMA = "aegis.asset-inventory/1"
MAX_FILES = 200_000
MAX_TREE_BYTES = 24_000_000
ANCHORS = (
    "AGENTS.md", "ASSETS.md", "REPO_MAP.md", "INDEX.md",
    "sovereign-omega-v2/ARTIFACT_REGISTRY.md",
    "sovereign-omega-v2/AGENTS.md", "agents/agent_registry.json",
    "harness/skill_tree.json", "scripts/agent_context.py",
)
EXTERNAL = ("google_drive", "library", "private_repositories", "other_branches",
            "datasets_not_in_git", "live_deployments", "research_publishers",
            "human_expertise")
TOKENS = re.compile(r"[a-z0-9]{3,}")
SUFFIXES = {
    "code": (".py", ".rs", ".ts", ".tsx", ".js", ".go", ".swift", ".sh"),
    "proofs": (".lean", ".v", ".rocq"),
    "datasets": (".csv", ".parquet", ".jsonl", ".arrow", ".sqlite"),
    "media_design": (".png", ".jpg", ".jpeg", ".svg", ".fig", ".mp4", ".webp", ".blend"),
    "documentation": (".md", ".pdf", ".docx", ".pptx", ".txt"),
}
PATH_GROUPS = {
    "agents": ("agents/", "harness/", "paperclip/"),
    "memory": ("memory/", "knowledge/", "research/", "sovereign-omega-v2/research/"),
    "security": ("security/", "alignment/", "sovereign-guard/"),
    "operations": (".github/workflows/", "supabase/", "terraform/", "vertex/"),
    "business": ("hub/", "content-calendar/", "enterprise/"),
    "science": ("genomics/", "formal/", "AegisRH/"),
    "user_experience": ("studio/", "cockpit/", "tactical/", "clients/"),
    "tests": ("test/", "tests/", "sovereign-omega-v2/test/", "agents/tests/"),
}


def git(root: Path, *args: str, timeout: int = 20) -> bytes:
    p = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=timeout, check=False)
    if p.returncode:
        raise ValueError("git " + args[0] + " failed: " +
                         p.stderr.decode("utf-8", "replace")[:160])
    return p.stdout


def classify(path: str) -> list[str]:
    p = path.lower()
    labels = [category for category, suffixes in SUFFIXES.items()
              if p.endswith(suffixes)]
    labels += [category for category, prefixes in PATH_GROUPS.items()
               if p.startswith(prefixes) or "/" + category + "/" in p]
    if "/test" in p or p.startswith("test"):
        labels.append("tests")
    return sorted(set(labels or ["other"]))


def inventory(root: Path, task: str, limit: int = 20) -> dict:
    if not isinstance(task, str) or not task.strip() or len(task) > 1000:
        raise ValueError("task must contain 1..1000 nonblank characters")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    head = git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head):
        raise ValueError("Git HEAD identity unverified")
    raw = git(root, "ls-tree", "-r", "-z", "--name-only", head)
    if len(raw) > MAX_TREE_BYTES:
        raise ValueError("Git tree exceeds inventory byte bound")
    names = raw.split(b"\0")
    if names[-1] != b"":
        raise ValueError("Git inventory truncated")
    paths = [p.decode("utf-8", "strict") for p in names[:-1]]
    if len(paths) > MAX_FILES or len(paths) != len(set(paths)):
        raise ValueError("Invalid or oversized Git inventory")
    present = set(paths)
    counts: dict[str, int] = {}
    for path in paths:
        for label in classify(path):
            counts[label] = counts.get(label, 0) + 1
    anchors = {key: {"state": "PRESENT_IN_GIT_HEAD" if key in present else "ABSENT_FROM_GIT_HEAD"}
               for key in ANCHORS}
    for key in ANCHORS:
        if key in present:
            payload = git(root, "show", f"{head}:{key}", timeout=10)
            anchors[key]["sha256"] = hashlib.sha256(payload).hexdigest()
    registry = {"state": "UNKNOWN", "declared_roles": None, "runtime_tested": False}
    if "agents/agent_registry.json" in present:
        try:
            data = json.loads(git(root, "show", f"{head}:agents/agent_registry.json"))
            if isinstance(data, dict) and all(isinstance(k, str) and isinstance(v, str)
                                              for k, v in data.items()):
                registry = {"state": "DECLARED_ONLY", "declared_roles": len(data),
                            "runtime_tested": False}
            else:
                registry["state"] = "INVALID_REGISTRY_SCHEMA"
        except (ValueError, UnicodeError):
            registry["state"] = "INVALID_REGISTRY_JSON"
    words = set(TOKENS.findall(task.lower()))
    candidates = []
    for path in paths:
        segments = set(TOKENS.findall(path.lower()))
        overlap = len(words & segments)
        if overlap:
            candidates.append((-overlap, path))
    candidates.sort()
    dirty = bool(git(root, "status", "--porcelain", "--untracked-files=no"))
    return {
        "schema": SCHEMA, "source": {"kind": "LOCAL_GIT_TREE", "head": head,
                                      "tracked_files": len(paths), "dirty_worktree_excluded": dirty},
        "task": task, "modalities": dict(sorted(counts.items())), "anchors": anchors,
        "agent_registry": registry,
        "candidate_paths": [{"path": p, "labels": classify(p),
                             "state": "NAME_MATCH_NOT_CONTENT_REVIEWED"}
                            for _, p in candidates[:limit]],
        "candidate_search": "PATH_TOKENS_ONLY_NOT_SEMANTIC_RECALL",
        "external_coverage": {kind: "NOT_INSPECTED" for kind in EXTERNAL},
        "reuse_status": "NOT_VERIFIED", "standard_conformance": "NOT_VERIFIED",
        "external_benchmark": "NOT_RUN", "world_best": "NOT_ESTABLISHED",
        "authority_effect": "NONE", "disposition": "LOCAL_GIT_HEAD_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    try:
        receipt = inventory(args.root.resolve(), args.task, args.limit)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"schema": SCHEMA, "disposition": "INVENTORY_FAILED",
                          "reason": str(exc), "authority_effect": "NONE"}, sort_keys=True))
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
