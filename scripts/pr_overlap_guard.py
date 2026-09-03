#!/usr/bin/env python3
"""Refuse a pull request that duplicates an already-open one.

EPISTEMIC TIER: T2. The overlap measure is deterministic and testable; the
thresholds are policy choices, not derived results.

WHY THIS EXISTS. On 2026-09-02 this repository accumulated ~20 new pull requests
in a day against a protected `main` that was merging none of them. The result was
119 open PRs in which one cognitive-recovery change was spread over five, agent
dispatch over four, and a single dashboard feature written twice from scratch by
two sessions that never checked whether the other existed. Closing duplicates by
hand does not stop the next one being opened an hour later. This does: an agent
that opens a PR overlapping an open one is told so at once, by name and number.

TWO SIGNALS, because exact-filename overlap alone misses the worst case.

  file overlap       the same paths edited in two open PRs
  territory overlap  the same top-level directory *created* by two open PRs

The dashboard pair is why the second signal is needed. One PR added
`production-cookbook/src/App.tsx`, the other `production-cookbook/src/main.jsx`.
They shared no file path at all, could not both merge, and a file-only check
would have passed both.

GENERATED PATHS ARE EXCLUDED. Every branch rewrites `.claude.json` and the
lockfiles; counting those would fire on every pull request and the check would be
ignored within a day. A guard nobody reads is worse than no guard.

WHAT THIS DOES NOT DO. It does not decide which PR is right, and it does not
close anything. It reports the collision and fails, so a person looks. A
deliberate stack of related PRs is legitimate and is meant to be waved through
with the documented label.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

API = "https://api.github.com"

#: Paths every branch touches. Overlap here carries no information.
GENERATED = (
    ".claude.json",
    "skill-hashes.sha256",
    ".claude/skill-hashes.sha256",
    "INDEX.md",
    "README.md",
    "package-lock.json",
    "Cargo.lock",
    "poetry.lock",
    "uv.lock",
)

#: Applied to a PR that is a deliberate continuation rather than a rediscovery.
OVERRIDE_LABEL = "stacked-pr"


def is_generated(path: str) -> bool:
    """True for paths a refresh bot or a lockfile writer rewrites on every branch."""
    return path in GENERATED or path.endswith(("/package-lock.json", "/Cargo.lock"))


def significant(paths: set[str]) -> set[str]:
    return {p for p in paths if not is_generated(p)}


def territory(files: list[dict], existing: frozenset[str]) -> set[str]:
    """Top-level directories this PR brings into existence.

    `existing` is the set of top-level directories already on the base branch,
    and excluding them is the whole point. A first version of this counted every
    top-level directory of an added file, and firing it against the live
    repository reported that 67 of 119 open PRs collided because they all
    "create `.github`" and "create `scripts`". Those directories have existed
    for months; adding a file inside one is ordinary work.

    What is not ordinary is two open PRs both inventing `production-cookbook/`.
    That is the case this signal exists for, and it is only visible against the
    base tree.
    """
    out: set[str] = set()
    for entry in files:
        if entry.get("status") != "added":
            continue
        path = entry.get("filename", "")
        head, sep, _ = path.partition("/")
        if sep and head not in existing and not is_generated(path):
            out.add(head)
    return out


def base_directories(root: str = ".") -> frozenset[str]:
    """Top-level directories of the checked-out base tree."""
    try:
        return frozenset(
            name
            for name in os.listdir(root)
            if os.path.isdir(os.path.join(root, name)) and name != ".git"
        )
    except OSError:
        return frozenset()


@dataclass(frozen=True)
class Collision:
    number: int
    title: str
    shared_files: tuple[str, ...]
    shared_territory: tuple[str, ...]
    jaccard: float

    def reason(self) -> str:
        if self.shared_territory:
            return f"both create `{'`, `'.join(self.shared_territory)}`"
        return f"{len(self.shared_files)} shared files, {self.jaccard:.0%} overlap"


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def collide(
    candidate_files: list[dict],
    others: list[tuple[int, str, list[dict]]],
    *,
    min_shared: int,
    min_jaccard: float,
    existing: frozenset[str] = frozenset(),
) -> list[Collision]:
    """Pure decision function. `others` is (number, title, files) per open PR.

    A territory collision reports on its own: two PRs inventing the same new
    top-level directory is decisive even when no single path matches.
    """
    mine = significant({e.get("filename", "") for e in candidate_files})
    my_land = territory(candidate_files, existing)

    found: list[Collision] = []
    for number, title, files in others:
        theirs = significant({e.get("filename", "") for e in files})
        shared = mine & theirs
        land = my_land & territory(files, existing)
        score = jaccard(mine, theirs)
        if land or (len(shared) >= min_shared and score >= min_jaccard):
            found.append(
                Collision(
                    number=number,
                    title=title,
                    shared_files=tuple(sorted(shared)),
                    shared_territory=tuple(sorted(land)),
                    jaccard=score,
                )
            )
    return sorted(found, key=lambda c: (-len(c.shared_territory), -c.jaccard))


def render(candidate: int, collisions: list[Collision]) -> str:
    if not collisions:
        return f"PR #{candidate} overlaps no open pull request."
    lines = [
        f"PR #{candidate} overlaps {len(collisions)} open pull request(s):",
        "",
    ]
    for c in collisions:
        lines.append(f"  #{c.number}  {c.title}")
        lines.append(f"      {c.reason()}")
        for path in c.shared_files[:8]:
            lines.append(f"      - {path}")
        if len(c.shared_files) > 8:
            lines.append(f"      - ... and {len(c.shared_files) - 8} more")
        lines.append("")
    lines.append(
        f"Close the duplicate, fold the work into the existing PR, or apply the "
        f"`{OVERRIDE_LABEL}` label if this is a deliberate continuation."
    )
    return "\n".join(lines)


def _get(url: str, token: str) -> list[dict]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "aegis-pr-overlap-guard",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch(repo: str, token: str, candidate: int) -> tuple[list[dict], list[tuple[int, str, list[dict]]]]:
    open_prs = _get(f"{API}/repos/{repo}/pulls?state=open&per_page=100", token)
    candidate_files = _get(f"{API}/repos/{repo}/pulls/{candidate}/files?per_page=100", token)
    others = [
        (pr["number"], pr["title"], _get(f"{API}/repos/{repo}/pulls/{pr['number']}/files?per_page=100", token))
        for pr in open_prs
        if pr["number"] != candidate
        and not any(label["name"] == OVERRIDE_LABEL for label in pr.get("labels", []))
    ]
    return candidate_files, others


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--min-shared", type=int, default=2)
    parser.add_argument("--min-jaccard", type=float, default=0.34)
    parser.add_argument(
        "--root",
        default=".",
        help="Checked-out base tree, read to learn which top-level directories already exist.",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or not args.repo:
        print("GITHUB_TOKEN and --repo/GITHUB_REPOSITORY are required.", file=sys.stderr)
        return 2

    try:
        candidate_files, others = fetch(args.repo, token, args.pr)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        # Fail loudly rather than silently passing: an unreachable API is not
        # evidence that the PR is unique.
        print(f"GitHub API unreachable: {exc}", file=sys.stderr)
        return 2

    collisions = collide(
        candidate_files,
        others,
        min_shared=args.min_shared,
        min_jaccard=args.min_jaccard,
        existing=base_directories(args.root),
    )
    print(render(args.pr, collisions))
    return 1 if collisions else 0


if __name__ == "__main__":
    raise SystemExit(main())
