#!/usr/bin/env python3
"""Generate the canonical Coq inventory for formal/theories.

The global attestation lane compiles every source under formal/theories with
`cd <dir> && coqc <file>` and then asserts that every file discovered on disk
has a COMPILED status.  Until now the compile ORDER was a hand-maintained list
inside the workflow, so a new module that was not appended by hand was
discovered, never compiled, and counted as a compile failure (#358), or had to
be registered pre-emptively by the author (#359).

This script removes that class of defect: it discovers every .v file, reads its
intra-repository `Require` edges, checks the graph is acyclic, and emits a
deterministic topological compile order together with each file's evidence
classification from formal/coq-inventory-policy.json.  It is fail-closed: an
unclassified file, a dangling policy entry, a cross-directory Require (which
the `cd <dir>` compile model cannot resolve), or a dependency cycle is an
error, not a warning.

Usage:
  scripts/coq_inventory.py                      # write formal/coq-inventory.json
  scripts/coq_inventory.py --check              # exit 1 if the committed file is stale
  scripts/coq_inventory.py --verify-with-coqdep # also cross-check edges against coqdep

Only the Python standard library is required, so --check runs on a bare runner
before any Coq toolchain is installed.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
CLASSIFICATIONS = ("REQUIRE_AXIOM_FREE", "DIAGNOSTIC_ONLY", "AUTHORITY_ELIGIBLE")

# `Require Import A B.`, `Require Export A.`, `From X Require Import A.`
REQUIRE_RE = re.compile(
    r"^\s*(?:From\s+(?P<prefix>[A-Za-z0-9_.]+)\s+)?Require(?:\s+(?:Import|Export))?\s+(?P<names>[^.]+?)\s*\.",
    re.MULTILINE,
)
COMMENT_RE = re.compile(r"\(\*.*?\*\)", re.DOTALL)


def strip_comments(text: str) -> str:
    # Coq comments nest; a single regex pass is enough for the flat comments
    # used in this corpus, and a nested comment would only hide a Require,
    # which is exactly the direction --verify-with-coqdep catches.
    prev = None
    while prev != text:
        prev, text = text, COMMENT_RE.sub(" ", text)
    return text


def discover(formal_root: Path) -> list[Path]:
    return sorted(p.relative_to(formal_root) for p in formal_root.rglob("*.v"))


def intra_repo_requires(formal_root: Path, rel: Path, known: set[Path]) -> list[str]:
    """Names required by `rel` that resolve to a sibling .v in the same directory."""
    text = strip_comments((formal_root / rel).read_text(encoding="utf-8"))
    out: list[str] = []
    for m in REQUIRE_RE.finditer(text):
        if m.group("prefix"):
            # `From Coq Require ...`, `From CoRN Require ...` are external by
            # construction: nothing in this tree is addressed by a prefix.
            continue
        for name in m.group("names").split():
            sibling = rel.parent / f"{name}.v"
            if sibling in known:
                if name not in out:
                    out.append(name)
            else:
                # Could the name resolve to a .v in ANOTHER directory?  The
                # compile model (`cd <dir> && coqc`) could not load it, so that
                # is a hard error rather than an external dependency.
                elsewhere = [k for k in known if k.name == f"{name}.v" and k.parent != rel.parent]
                if elsewhere:
                    raise SystemExit(
                        f"{rel}: requires {name}, which exists only in "
                        f"{', '.join(map(str, elsewhere))}; the attestation lane compiles "
                        f"per directory and cannot resolve cross-directory Requires"
                    )
    return out


def toposort(files: list[Path], edges: dict[Path, list[str]]) -> list[Path]:
    """Kahn's algorithm with a sorted frontier, so the order is a pure function
    of the file set and edge set (no dict-order or filesystem-order leakage)."""
    deps: dict[Path, set[Path]] = {
        f: {f.parent / f"{n}.v" for n in edges[f]} for f in files
    }
    remaining = set(files)
    order: list[Path] = []
    while remaining:
        ready = sorted(f for f in remaining if not (deps[f] & remaining))
        if not ready:
            cyc = sorted(map(str, remaining))
            raise SystemExit(f"dependency cycle among: {', '.join(cyc)}")
        for f in ready:
            order.append(f)
            remaining.remove(f)
    return order


def load_policy(path: Path, files: list[Path]) -> dict[Path, str]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    classification: dict[Path, str] = {}
    for cls in CLASSIFICATIONS:
        for entry in policy.get(cls, []):
            p = Path(entry)
            if p not in set(files):
                raise SystemExit(f"policy lists {entry} under {cls}, but no such file exists")
            if p in classification:
                raise SystemExit(f"policy lists {entry} under both {classification[p]} and {cls}")
            classification[p] = cls
    missing = [str(f) for f in files if f not in classification]
    if missing:
        raise SystemExit(
            "unclassified source(s) — add each to exactly one of "
            f"{'/'.join(CLASSIFICATIONS)} in {path}: {', '.join(missing)}"
        )
    return classification


def build(formal_root: Path, policy_path: Path) -> dict:
    files = discover(formal_root)
    known = set(files)
    edges = {f: intra_repo_requires(formal_root, f, known) for f in files}
    order = toposort(files, edges)
    classification = load_policy(policy_path, files)
    entries = [
        {
            "path": f.as_posix(),
            "directory": f.parent.as_posix(),
            "module": f.stem,
            "requires": edges[f],
            "classification": classification[f],
        }
        for f in order
    ]
    counts = {cls: sum(1 for e in entries if e["classification"] == cls) for cls in CLASSIFICATIONS}
    return {
        "schema_version": SCHEMA_VERSION,
        "formal_root": formal_root.as_posix(),
        "compile_model": "cd <directory> && coqc <file>; intra-directory Requires only",
        "file_count": len(entries),
        "counts": counts,
        "compile_order": [e["path"] for e in entries],
        "files": entries,
    }


def verify_with_coqdep(formal_root: Path, inventory: dict) -> None:
    coqdep = shutil.which("coqdep")
    if not coqdep:
        raise SystemExit("--verify-with-coqdep requested but coqdep is not on PATH")
    mismatches = []
    for e in inventory["files"]:
        d = formal_root / e["directory"]
        out = subprocess.run(
            [coqdep, "-Q", ".", "", Path(e["path"]).name],
            cwd=d, capture_output=True, text=True, check=False,
        ).stdout
        # first line: "<mod>.vo <mod>.glob ... : <mod>.v Dep1.vo Dep2.vo"
        first = out.splitlines()[0] if out.strip() else ""
        rhs = first.split(":", 1)[1] if ":" in first else ""
        found = sorted(
            Path(tok).stem for tok in rhs.split() if tok.endswith(".vo")
        )
        expected = sorted(e["requires"])
        if found != expected:
            mismatches.append(f"{e['path']}: regex={expected} coqdep={found}")
    if mismatches:
        raise SystemExit("coqdep disagrees with the regex parser:\n  " + "\n  ".join(mismatches))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--formal-root", default="formal/theories", type=Path)
    ap.add_argument("--policy", default="formal/coq-inventory-policy.json", type=Path)
    ap.add_argument("--out", default="formal/coq-inventory.json", type=Path)
    ap.add_argument("--check", action="store_true", help="fail if --out is missing or stale")
    ap.add_argument("--verify-with-coqdep", action="store_true")
    args = ap.parse_args()

    inventory = build(args.formal_root, args.policy)
    if args.verify_with_coqdep:
        verify_with_coqdep(args.formal_root, inventory)

    rendered = json.dumps(inventory, indent=2, sort_keys=False) + "\n"
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else None
        if current != rendered:
            sys.stderr.write(
                f"{args.out} is stale or missing; regenerate with: "
                f"python3 {Path(sys.argv[0]).as_posix()}\n"
            )
            return 1
        print(f"{args.out}: up to date ({inventory['file_count']} files)")
        return 0
    args.out.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.out} ({inventory['file_count']} files, {len(inventory['compile_order'])} in order)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
