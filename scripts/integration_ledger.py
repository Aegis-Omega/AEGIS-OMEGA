#!/usr/bin/env python3
"""
Commit-bound integration ledger.

The ledger classifies top-level repository areas as WIRED, LINKED, DORMANT, or
ORPHAN from repository evidence. It emits deterministic Markdown and JSON bound
to the exact commit, source tree, generator version, and generator digest.

Examples:
    python3 scripts/integration_ledger.py
    python3 scripts/integration_ledger.py --json
    python3 scripts/integration_ledger.py --write
    python3 scripts/integration_ledger.py --write --output-dir artifacts/ledger \
        --expected-sha "$GITHUB_SHA"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from collections import Counter
from typing import Iterable, Sequence

SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = "2.1.0"
STATUS_ORDER = ("WIRED", "LINKED", "DORMANT", "ORPHAN")
SKIP = {
    ".git",
    "node_modules",
    "target",
    ".github",
    ".claude",
    ".vercel",
    "dist",
    "build",
    "__pycache__",
    "coverage",
    ".venv",
}


def sh(args: Sequence[str], *, timeout: int = 90) -> str:
    """Return stdout from a bounded command, or an empty string on failure."""
    try:
        completed = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def git_value(*args: str) -> str:
    return sh(["git", "--no-replace-objects", *args]).strip()


def git_bytes(*args: str) -> bytes:
    """Read real Git objects and propagate failures instead of emitting evidence."""
    return subprocess.run(
        ["git", "--no-replace-objects", *args],
        check=True,
        capture_output=True,
        timeout=90,
    ).stdout


def validate_commit(commit: str) -> None:
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise ValueError("source must be a full lowercase commit object ID")
    if git_bytes("cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("source object is not a commit")


def head_sha() -> str:
    return git_value("rev-parse", "HEAD") or "unknown"


def repository_name() -> str:
    configured = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if configured:
        return configured
    remote = git_value("config", "--get", "remote.origin.url")
    if not remote:
        return "unknown"
    remote = remote.removesuffix(".git")
    if remote.startswith("git@") and ":" in remote:
        remote = remote.split(":", 1)[1]
    elif "://" in remote:
        remote = remote.split("://", 1)[1].split("/", 1)[-1]
    return remote.strip("/") or "unknown"


def generator_digest() -> str:
    """Identify the executed generator bytes, including local development edits."""
    data = Path(__file__).resolve().read_bytes()
    return hashlib.sha256(data).hexdigest()


def committed_rows(commit: str) -> list[tuple[str, str, str]]:
    """Classify committed blobs only; configuration is not execution evidence."""
    validate_commit(commit)
    entries = git_bytes("ls-tree", "--full-tree", "-r", "-z", commit).split(b"\0")
    files: dict[str, str] = {}
    directories: set[str] = set()
    for entry in entries:
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = header.split()
        path = raw_path.decode("utf-8", errors="strict")
        top = path.split("/", 1)[0]
        if "/" in path and top not in SKIP and not top.startswith("."):
            directories.add(top)
        if (
            kind != b"blob"
            or mode not in (b"100644", b"100755")
            or any(part in SKIP - {".github"} for part in path.split("/")[:-1])
            or path.lower().endswith(".md")
        ):
            continue
        data = git_bytes("cat-file", "blob", oid.decode("ascii"))
        if b"\0" not in data:
            files[path] = data.decode("utf-8", errors="replace")

    rows = []
    for directory in sorted(directories):
        # References are lexical observations, never proof a command ran.
        refs = sum(
            directory + "/" in text
            for path, text in files.items()
            if not path.startswith(directory + "/")
        )
        configured = directory + "/vercel.json" in files
        status = "LINKED" if configured or refs >= 3 else "DORMANT" if refs else "ORPHAN"
        evidence = []
        if configured:
            evidence.append("committed deployment configuration; execution unverified")
        if refs:
            evidence.append(f"{refs} committed lexical references; execution unverified")
        rows.append((status, directory, ", ".join(evidence) or "no reference found in scanned committed text"))
    return sorted(rows, key=lambda row: (STATUS_ORDER.index(row[0]), row[1]))


def build_rows() -> list[tuple[str, str, str]]:
    return committed_rows(head_sha())


def metadata() -> dict[str, object]:
    commit = head_sha()
    validate_commit(commit)
    return {
        "schema_version": SCHEMA_VERSION,
        "repository": repository_name(),
        "commit_sha": commit,
        "tree_sha": git_bytes("rev-parse", commit + "^{tree}").decode("ascii").strip(),
        "source_timestamp": git_bytes("show", "-s", "--format=%cI", commit).decode("ascii").strip(),
        "generator": {
            "path": "scripts/integration_ledger.py",
            "version": GENERATOR_VERSION,
            "sha256": generator_digest(),
        },
    }


def build_document(
    rows: Iterable[tuple[str, str, str]],
    meta: dict[str, object] | None = None,
) -> dict[str, object]:
    row_list = list(rows)
    counts = Counter(status for status, _, _ in row_list)
    document: dict[str, object] = dict(meta or metadata())
    document["scope"] = "top-level-area"
    document["status_order"] = list(STATUS_ORDER)
    document["counts"] = {status: counts.get(status, 0) for status in STATUS_ORDER}
    document["area_count"] = len(row_list)
    document["areas"] = [
        {"status": status, "area": area, "evidence": evidence}
        for status, area, evidence in row_list
    ]
    return document


def render_json(document: dict[str, object]) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_md(document: dict[str, object]) -> str:
    counts = document["counts"]
    generator = document["generator"]
    assert isinstance(counts, dict)
    assert isinstance(generator, dict)
    lines = [
        "# Integration Ledger",
        "",
        (
            f"**Schema `{document['schema_version']}` · repository `{document['repository']}` · "
            f"commit `{document['commit_sha']}` · tree `{document['tree_sha']}`**"
        ),
        "",
        (
            f"Generated by `scripts/integration_ledger.py` v{generator['version']} "
            f"(`sha256:{generator['sha256']}`) from source timestamp "
            f"`{document['source_timestamp']}`. Do not hand-edit."
        ),
        "",
        (
            f"**{counts['WIRED']} WIRED · {counts['LINKED']} LINKED · "
            f"{counts['DORMANT']} DORMANT · {counts['ORPHAN']} ORPHAN** "
            f"across {document['area_count']} top-level areas."
        ),
        "",
        "| Status | Area | Evidence |",
        "|--------|------|----------|",
    ]
    areas = document["areas"]
    assert isinstance(areas, list)
    for item in areas:
        assert isinstance(item, dict)
        lines.append(f"| {item['status']} | `{item['area']}` | {item['evidence']} |")
    lines += [
        "",
        "## What the statuses mean",
        "",
        "- **WIRED** — reserved for separately verified execution; this static generator never emits it.",
        "- **LINKED** — committed deployment configuration or at least three lexical references; execution unverified.",
        "- **DORMANT** — referenced by one or two external files.",
        "- **ORPHAN** — no reference found in the scanned committed text.",
        "",
        "> Static, top-level observations only: regular committed text blobs, excluding Markdown and dependency/build trees. Symlinks, submodule contents and NUL-containing binary blobs are not scanned. Execution and reachability remain unverified.",
        "",
    ]
    return "\n".join(lines)


def validate_expected_sha(actual: str, expected: str) -> None:
    expected = expected.strip()
    if not expected:
        return
    if actual != expected:
        raise ValueError(f"ledger commit mismatch: generated={actual} expected={expected}")


def validate_document(document: dict[str, object]) -> None:
    commit = str(document.get("commit_sha", ""))
    tree = str(document.get("tree_sha", ""))
    digest = str(document.get("generator", {}).get("sha256", "")) if isinstance(document.get("generator"), dict) else ""
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise ValueError(f"invalid commit_sha: {commit!r}")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", tree):
        raise ValueError(f"invalid tree_sha: {tree!r}")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("invalid generator sha256")
    areas = document.get("areas")
    if not isinstance(areas, list):
        raise ValueError("areas must be a list")
    expected_order = sorted(
        areas,
        key=lambda item: (STATUS_ORDER.index(str(item["status"])), str(item["area"])),
    )
    if areas != expected_order:
        raise ValueError("areas are not deterministically ordered")


def write_outputs(document: dict[str, object], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "INTEGRATION_LEDGER.md"
    json_path = output_dir / "INTEGRATION_LEDGER.json"
    markdown_path.write_text(render_md(document), encoding="utf-8")
    json_path.write_text(render_json(document), encoding="utf-8")
    return markdown_path, json_path


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write Markdown and JSON outputs")
    parser.add_argument("--json", action="store_true", help="print the canonical JSON document")
    parser.add_argument("--output-dir", default=".", help="directory for generated files")
    parser.add_argument(
        "--expected-sha",
        default=os.environ.get("AEGIS_EXPECTED_SHA", ""),
        help="fail when generated commit does not exactly match this SHA",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    meta = metadata()
    validate_expected_sha(str(meta["commit_sha"]), args.expected_sha)
    document = build_document(committed_rows(str(meta["commit_sha"])), meta)
    validate_document(document)

    if args.json:
        print(render_json(document), end="")
    else:
        print(f"{'STATUS':8} {'AREA':26} EVIDENCE")
        print("-" * 66)
        for item in document["areas"]:
            print(f"{item['status']:8} {item['area']:26} {item['evidence']}")

    if args.write:
        markdown_path, json_path = write_outputs(document, Path(args.output_dir))
        print(f"\nwrote {markdown_path}")
        print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
