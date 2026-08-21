#!/usr/bin/env bash
set -euo pipefail

REPO="."
MAIN="origin/main"
OUT=""
REFRESH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --main) MAIN="$2"; shift 2 ;;
    --json) OUT="$2"; shift 2 ;;
    --refresh) REFRESH=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done

if [[ -z "$OUT" ]]; then
  echo 'missing --json <path>' >&2
  exit 64
fi

REPO="$(cd "$REPO" && pwd)"

if [[ $REFRESH -eq 1 ]]; then
  if [[ "$(git -C "$REPO" rev-parse --is-shallow-repository 2>/dev/null || echo true)" == "true" ]]; then
    git -C "$REPO" fetch --all --prune --tags --unshallow --force
  else
    git -C "$REPO" fetch --all --prune --tags --force
  fi
fi

if ! git -C "$REPO" rev-parse --verify "$MAIN^{commit}" >/dev/null 2>&1; then
  echo "main ref not found: $MAIN" >&2
  exit 65
fi

mkdir -p "$(dirname "$OUT")"

python3 - "$REPO" "$MAIN" "$OUT" <<'PY'
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

repo, main_ref, out = sys.argv[1:]


def git(*args: str, check: bool = True) -> str:
    p = subprocess.run(
        ["git", "-C", repo, *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


main_sha = git("rev-parse", f"{main_ref}^{{commit}}")
shallow = git("rev-parse", "--is-shallow-repository") == "true"

# Build one logical branch namespace. Prefer local heads over matching origin/* refs,
# but include remote-only branches. Ignore remote symbolic HEAD.
logical: dict[str, str] = {}
for line in git("for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes").splitlines():
    ref = line.strip()
    if not ref or ref.endswith("/HEAD"):
        continue
    if ref.startswith("refs/heads/"):
        name = ref[len("refs/heads/"):]
        logical[name] = ref
    elif ref.startswith("refs/remotes/"):
        rest = ref[len("refs/remotes/"):]
        if "/" not in rest:
            continue
        remote, name = rest.split("/", 1)
        logical.setdefault(name, ref)

branches = []
for name, ref in sorted(logical.items()):
    sha = git("rev-parse", f"{ref}^{{commit}}")
    ahead = int(git("rev-list", "--count", f"{main_ref}..{ref}"))
    behind = int(git("rev-list", "--count", f"{ref}..{main_ref}"))
    branches.append(
        {
            "branch": name,
            "ref": ref,
            "tip": sha,
            "ahead_of_main": ahead,
            "behind_main": behind,
            "contained_in_main": ahead == 0,
        }
    )

all_ref_count = int(git("rev-list", "--all", "--count"))
main_count = int(git("rev-list", main_ref, "--count"))
off_main_count = int(git("rev-list", "--all", "--not", main_ref, "--count"))

# Unique off-main commits are the key epistemic quantity. Also retain a bounded
# sample of their identities so a model can prove the universe is not abstract.
off_main_lines = git(
    "log",
    "--all",
    f"^{main_ref}",
    "--date=iso-strict",
    "--format=%H%x09%ad%x09%s",
).splitlines()
sample = []
for line in off_main_lines[:200]:
    parts = line.split("\t", 2)
    if len(parts) == 3:
        sample.append({"sha": parts[0], "date": parts[1], "subject": parts[2]})

payload = {
    "schema_version": "AEGIS_REPO_UNIVERSE_V1",
    "authority": "REACHABILITY_EVIDENCE_ONLY",
    "repository_root": repo,
    "main_ref": main_ref,
    "main_sha": main_sha,
    "history_complete": not shallow,
    "branch_count": len(branches),
    "all_ref_commit_count": all_ref_count,
    "main_reachable_commit_count": main_count,
    "commits_not_reachable_from_main": off_main_count,
    "off_main_sample_truncated": len(off_main_lines) > len(sample),
    "off_main_commit_sample": sample,
    "branches": branches,
    "epistemic_rule": (
        "canonical main defines admitted state, not artifact existence; "
        "off-main reachable commits must be searched before any global absence claim"
    ),
}

Path(out).write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "schema_version": payload["schema_version"],
    "history_complete": payload["history_complete"],
    "branch_count": payload["branch_count"],
    "all_ref_commit_count": payload["all_ref_commit_count"],
    "main_reachable_commit_count": payload["main_reachable_commit_count"],
    "commits_not_reachable_from_main": payload["commits_not_reachable_from_main"],
    "main_sha": payload["main_sha"],
}, sort_keys=True))
PY
