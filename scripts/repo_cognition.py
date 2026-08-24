#!/usr/bin/env python3
"""AEGIS repository cognition: complete, deterministic, fail-closed source census.

This module deliberately separates two concepts that were previously conflated:

* repository cognition: what files/content exist in the exact Git source corpus;
* repository authority: which files/policies may authorize a mutation.

`INDEX.md` remains an authority/policy surface. It is not a complete file census.
The generated manifest covers every Git-tracked HEAD entry except the manifest
itself, which is excluded to avoid a cryptographic self-reference cycle.

The aggregate `corpus_root` is content-addressed and stable across commits that
only refresh the generated manifest. A runtime receipt may bind that root to the
current HEAD without putting the volatile commit SHA inside the committed
manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "AEGIS_REPO_COGNITION_V1"
GENERATOR_VERSION = "1.0.0"
DEFAULT_MANIFEST_PATH = ".aegis/repo-cognition-v1.json"
GENERATED_PATHS = frozenset({DEFAULT_MANIFEST_PATH})

_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript-react",
    ".js": "javascript",
    ".jsx": "javascript-react",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".c": "c",
    ".h": "c-header",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp-header",
    ".cs": "csharp",
    ".swift": "swift",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "powershell",
    ".md": "markdown",
    ".mdx": "markdown",
    ".json": "json",
    ".jsonl": "jsonl",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".proto": "protobuf",
    ".v": "coq",
    ".tex": "latex",
}

_SYMBOL_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "python": (
        re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)", re.MULTILINE),
    ),
    "typescript": (
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|type|enum|namespace)\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
        re.compile(r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
    ),
    "typescript-react": (
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|type|enum|namespace)\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
        re.compile(r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
    ),
    "javascript": (
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
        re.compile(r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
    ),
    "javascript-react": (
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
        re.compile(r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)", re.MULTILINE),
    ),
    "rust": (
        re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|enum|trait|mod|type)\s+([A-Za-z_]\w*)", re.MULTILINE),
    ),
    "go": (
        re.compile(r"^\s*(?:func|type)\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", re.MULTILINE),
    ),
    "coq": (
        re.compile(r"^\s*(?:Theorem|Lemma|Definition|Fixpoint|Inductive|Record|Class|Axiom|Parameter)\s+([A-Za-z_]\w*)", re.MULTILINE),
    ),
}

_DEPENDENCY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "python": (
        re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\s+", re.MULTILINE),
        re.compile(r"^\s*import\s+([A-Za-z_][\w.]*)", re.MULTILINE),
    ),
    "typescript": (
        re.compile(r"\bfrom\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    ),
    "typescript-react": (
        re.compile(r"\bfrom\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    ),
    "javascript": (
        re.compile(r"\bfrom\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    ),
    "javascript-react": (
        re.compile(r"\bfrom\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    ),
    "rust": (
        re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE),
        re.compile(r"^\s*(?:pub\s+)?mod\s+([A-Za-z_]\w*)\s*;", re.MULTILINE),
    ),
}


def _run_git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=root,
            input=input_bytes,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.output.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {message}") from exc


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _head_entries(root: Path) -> list[dict[str, str]]:
    raw = _run_git(root, "ls-tree", "-r", "-z", "--full-tree", "HEAD")
    entries: list[dict[str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path_raw = record.split(b"\t", 1)
        mode_raw, object_type_raw, object_sha_raw = meta.split(b" ", 2)
        entries.append(
            {
                "mode": mode_raw.decode("ascii"),
                "object_type": object_type_raw.decode("ascii"),
                "git_blob_sha": object_sha_raw.decode("ascii"),
                "path": path_raw.decode("utf-8", errors="surrogateescape"),
            }
        )
    return sorted(entries, key=lambda item: item["path"])


def _read_objects(root: Path, shas: Iterable[str]) -> dict[str, bytes]:
    ordered = list(dict.fromkeys(shas))
    if not ordered:
        return {}

    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    try:
        proc.stdin.write("".join(f"{sha}\n" for sha in ordered).encode("ascii"))
        proc.stdin.close()
        result: dict[str, bytes] = {}
        for expected_sha in ordered:
            header = proc.stdout.readline()
            if not header:
                error = proc.stderr.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"git cat-file ended early: {error}")
            parts = header.rstrip(b"\n").split()
            if len(parts) == 2 and parts[1] == b"missing":
                raise RuntimeError(f"git object missing: {expected_sha}")
            if len(parts) != 3:
                raise RuntimeError(f"unexpected git cat-file header: {header!r}")
            actual_sha = parts[0].decode("ascii")
            size = int(parts[2])
            if actual_sha != expected_sha:
                raise RuntimeError(
                    f"git cat-file order mismatch: expected {expected_sha}, got {actual_sha}"
                )
            data = proc.stdout.read(size)
            trailer = proc.stdout.read(1)
            if len(data) != size or trailer != b"\n":
                raise RuntimeError(f"truncated git object: {expected_sha}")
            result[expected_sha] = data
        return result
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def _language(path: str) -> str:
    name = Path(path).name.lower()
    if name in {"dockerfile", "containerfile"} or name.startswith("dockerfile."):
        return "dockerfile"
    if name in {"makefile", "gnumakefile"}:
        return "make"
    return _LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower(), "unknown")


def _kind(path: str, language: str) -> str:
    lower = path.lower()
    name = Path(path).name.lower()
    if "/test/" in f"/{lower}" or "/tests/" in f"/{lower}" or name.startswith("test_") or ".test." in name or ".spec." in name:
        return "test"
    if lower.startswith(".github/workflows/"):
        return "workflow"
    if language in {
        "python", "typescript", "typescript-react", "javascript", "javascript-react",
        "rust", "go", "java", "kotlin", "c", "c-header", "cpp", "cpp-header",
        "csharp", "swift", "shell", "powershell", "coq",
    }:
        return "source"
    if language in {"markdown", "latex"}:
        return "documentation"
    if language in {"json", "jsonl", "yaml", "toml", "sql", "graphql", "protobuf"}:
        return "config-or-data"
    if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".pdf", ".zip", ".wasm"}:
        return "asset"
    return "other"


def _text_metadata(data: bytes, language: str) -> tuple[int | None, list[str], list[str], str | None]:
    if b"\0" in data:
        return None, [], [], None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, [], [], None

    line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    symbol_hints: list[str] = []
    for pattern in _SYMBOL_PATTERNS.get(language, ()):
        for match in pattern.finditer(text):
            symbol = match.group(1).strip()
            if symbol and symbol not in symbol_hints:
                symbol_hints.append(symbol)
            if len(symbol_hints) >= 64:
                break
        if len(symbol_hints) >= 64:
            break

    dependency_hints: list[str] = []
    for pattern in _DEPENDENCY_PATTERNS.get(language, ()):
        for match in pattern.finditer(text):
            value = " ".join(match.group(1).split())
            if value and value not in dependency_hints:
                dependency_hints.append(value)
            if len(dependency_hints) >= 32:
                break
        if len(dependency_hints) >= 32:
            break

    heading_hint: str | None = None
    if language == "markdown":
        heading = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
        if heading:
            heading_hint = heading.group(1).strip()[:240]

    return line_count, symbol_hints, dependency_hints, heading_hint


def build_repository_corpus(root: Path) -> dict[str, Any]:
    """Build the complete deterministic source-corpus manifest for Git HEAD."""
    root = root.resolve()
    tracked = _head_entries(root)
    excluded_generated_paths = sorted(
        entry["path"] for entry in tracked if entry["path"] in GENERATED_PATHS
    )
    eligible = [entry for entry in tracked if entry["path"] not in GENERATED_PATHS]
    objects = _read_objects(root, (entry["git_blob_sha"] for entry in eligible))

    files: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []

    for entry in eligible:
        data = objects[entry["git_blob_sha"]]
        language = _language(entry["path"])
        line_count, symbols, dependencies, heading = _text_metadata(data, language)
        content_sha256 = _sha256(data)
        file_entry: dict[str, Any] = {
            "path": entry["path"],
            "mode": entry["mode"],
            "object_type": entry["object_type"],
            "git_blob_sha": entry["git_blob_sha"],
            "content_sha256": content_sha256,
            "size_bytes": len(data),
            "language": language,
            "kind": _kind(entry["path"], language),
            "line_count": line_count,
            "symbol_hints": symbols,
            "dependency_hints": dependencies,
            "heading_hint": heading,
        }
        files.append(file_entry)
        identity_rows.append(
            {
                "path": entry["path"],
                "mode": entry["mode"],
                "object_type": entry["object_type"],
                "git_blob_sha": entry["git_blob_sha"],
                "content_sha256": content_sha256,
                "size_bytes": len(data),
            }
        )

    indexed = len(files)
    eligible_count = len(eligible)
    coverage = 1.0 if indexed == eligible_count else (
        indexed / eligible_count if eligible_count else 1.0
    )
    corpus_root = _sha256(_canonical_bytes(identity_rows))

    return {
        "schema": SCHEMA,
        "generator": "scripts/repo_cognition.py",
        "generator_version": GENERATOR_VERSION,
        "root_scope": "canonical ordered array of path, mode, object_type, git_blob_sha, content_sha256, size_bytes",
        "coverage_scope": "all git-tracked HEAD entries except explicit generated self-reference paths",
        "authority_boundary": "repository cognition proves content identity/existence only; INDEX.md and admitted policies govern mutation authority",
        "tracked_file_count": len(tracked),
        "eligible_file_count": eligible_count,
        "indexed_file_count": indexed,
        "coverage": coverage,
        "excluded_generated_paths": excluded_generated_paths,
        "corpus_root": corpus_root,
        "files": files,
    }


def render_manifest(manifest: dict[str, Any]) -> str:
    return json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"


def verify_repository_corpus(root: Path, manifest_path: Path) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not manifest_path.exists():
        return False, [f"repository cognition manifest missing: {manifest_path}"]
    try:
        recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"repository cognition manifest unreadable: {exc}"]

    live = build_repository_corpus(root)
    if recorded.get("schema") != SCHEMA:
        reasons.append("repository cognition schema mismatch")
    if recorded.get("coverage") != 1.0:
        reasons.append("recorded repository coverage is incomplete")
    if live.get("coverage") != 1.0:
        reasons.append("live repository coverage is incomplete")
    if recorded.get("corpus_root") != live.get("corpus_root"):
        reasons.append(
            "repository cognition stale: recorded corpus_root does not match live Git HEAD source corpus"
        )
    for field in ("tracked_file_count", "eligible_file_count", "indexed_file_count"):
        if recorded.get(field) != live.get(field):
            reasons.append(f"repository cognition stale: {field} mismatch")
    if recorded.get("excluded_generated_paths") != live.get("excluded_generated_paths"):
        reasons.append("repository cognition stale: generated-path exclusion mismatch")

    return not reasons, reasons


def build_runtime_receipt(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    head = _run_git(root, "rev-parse", "HEAD").decode("ascii").strip()
    tree = _run_git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    return {
        "schema": "AEGIS_REPO_COGNITION_RECEIPT_V1",
        "repository_head": head,
        "repository_tree": tree,
        "corpus_root": manifest["corpus_root"],
        "tracked_file_count": manifest["tracked_file_count"],
        "eligible_file_count": manifest["eligible_file_count"],
        "indexed_file_count": manifest["indexed_file_count"],
        "coverage": manifest["coverage"],
        "authority": "CONTENT_IDENTITY_AND_ADDRESSABILITY_ONLY",
    }


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="fail if committed manifest is stale/incomplete")
    action.add_argument("--write", action="store_true", help="write the deterministic manifest (default)")
    parser.add_argument("--root", default=None, help="repository root")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, help="manifest path relative to repository root")
    parser.add_argument("--receipt", action="store_true", help="emit an exact-HEAD runtime receipt")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else _default_root()
    manifest_path = root / args.manifest

    if args.check:
        ok, reasons = verify_repository_corpus(root, manifest_path)
        if not ok:
            if not args.quiet:
                print("REPOSITORY_KNOWLEDGE_INCOMPLETE", file=sys.stderr)
                for reason in reasons:
                    print(f"  - {reason}", file=sys.stderr)
            return 1
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not args.quiet:
            print(
                "Repository cognition VERIFIED: "
                f"coverage={manifest['coverage']:.3f} "
                f"indexed={manifest['indexed_file_count']}/{manifest['eligible_file_count']} "
                f"root={manifest['corpus_root']}"
            )
    else:
        manifest = build_repository_corpus(root)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(render_manifest(manifest), encoding="utf-8", newline="\n")
        if not args.quiet:
            print(
                "Repository cognition WRITTEN: "
                f"coverage={manifest['coverage']:.3f} "
                f"indexed={manifest['indexed_file_count']}/{manifest['eligible_file_count']} "
                f"root={manifest['corpus_root']}"
            )

    if args.receipt:
        print(json.dumps(build_runtime_receipt(root, manifest), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
