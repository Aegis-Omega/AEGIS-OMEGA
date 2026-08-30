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
import datetime as dt
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
GENERATOR_VERSION = "2.0.0"
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
    return sh(["git", *args]).strip()


def head_sha() -> str:
    return git_value("rev-parse", "HEAD") or "unknown"


def tree_sha() -> str:
    return git_value("rev-parse", "HEAD^{tree}") or "unknown"


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


def source_timestamp() -> str:
    """Return a deterministic timestamp derived from the admitted source commit."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoch:
        try:
            value = dt.datetime.fromtimestamp(int(epoch), tz=dt.timezone.utc)
            return value.isoformat().replace("+00:00", "Z")
        except (ValueError, OverflowError):
            pass
    commit_time = git_value("show", "-s", "--format=%cI", "HEAD")
    return commit_time or "unknown"


def generator_digest() -> str:
    data = Path(__file__).resolve().read_bytes()
    return hashlib.sha256(data).hexdigest()


def workflow_text() -> str:
    directory = Path(".github/workflows")
    if not directory.is_dir():
        return ""
    output: list[str] = []
    for path in sorted(p for p in directory.iterdir() if p.is_file()):
        try:
            output.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError as exc:
            print(f"integration_ledger: skipping {path.name}: {exc}", file=sys.stderr)
    return "\n".join(output)


def external_refs(directory: str) -> int:
    """Count files outside directory that contain a reference to `directory/`."""
    output = sh(
        [
            "grep",
            "-rIl",
            "--exclude-dir=node_modules",
            "--exclude-dir=.git",
            "--exclude-dir=target",
            "--exclude-dir=__pycache__",
            f"{directory}/",
            ".",
        ]
    ).splitlines()
    return sum(
        1
        for filename in output
        if not filename.startswith(f"./{directory}/") and f"/{directory}/" not in filename
    )


def classify(directory: str, workflows: str) -> tuple[str, str]:
    in_ci = f"{directory}/" in workflows or (f" {directory}" in workflows and len(directory) > 3)
    has_vercel = Path(directory, "vercel.json").exists()
    references = external_refs(directory)
    evidence: list[str] = []
    if in_ci:
        evidence.append("CI")
    if has_vercel:
        evidence.append("vercel")
    if references:
        evidence.append(f"{references} ext-ref")
    if in_ci or has_vercel:
        return "WIRED", ", ".join(evidence)
    if references >= 3:
        return "LINKED", ", ".join(evidence)
    if references >= 1:
        return "DORMANT", ", ".join(evidence)
    return "ORPHAN", "no external reference"


def build_rows() -> list[tuple[str, str, str]]:
    workflows = workflow_text()
    directories = sorted(
        entry.name
        for entry in Path(".").iterdir()
        if entry.is_dir() and entry.name not in SKIP and not entry.name.startswith(".")
    )
    ranked = [
        (STATUS_ORDER.index(status), directory, status, evidence)
        for directory in directories
        for status, evidence in [classify(directory, workflows)]
    ]
    ranked.sort(key=lambda row: (row[0], row[1]))
    return [(status, directory, evidence) for _, directory, status, evidence in ranked]


def metadata() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "repository": repository_name(),
        "commit_sha": head_sha(),
        "tree_sha": tree_sha(),
        "source_timestamp": source_timestamp(),
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
        "- **WIRED** — a live entrypoint runs it through CI or a configured deployment surface.",
        "- **LINKED** — referenced by at least three external files but not independently exercised.",
        "- **DORMANT** — referenced by one or two external files.",
        "- **ORPHAN** — no reference exists outside the directory.",
        "",
        "> Classification is at top-level-area grain. A WIRED directory may still contain unreachable files.",
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
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ValueError(f"invalid commit_sha: {commit!r}")
    if not re.fullmatch(r"[0-9a-f]{40,64}", tree):
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
    args = parse_args(argv or sys.argv[1:])
    document = build_document(build_rows())
    validate_document(document)
    validate_expected_sha(str(document["commit_sha"]), args.expected_sha)

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
