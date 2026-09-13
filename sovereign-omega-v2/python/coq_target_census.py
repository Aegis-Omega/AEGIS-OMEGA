#!/usr/bin/env python3
"""Deterministic census for reviewed Coq source/explicit-declaration targets."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

KIND = "COQ_TARGET_MANIFEST_V1"
BINDING_SCOPE = "SOURCE_BYTES_AND_EXPLICIT_DECLARATIONS"
IDENT = r"[A-Za-z_][A-Za-z0-9_']*"
SINGLE_DECL_RE = re.compile(
    rf"(?m)^\s*(?:Definition|Fixpoint|CoFixpoint|Inductive|CoInductive|Record|Variant|Class|Theorem|Lemma|Corollary|Proposition|Fact|Remark)\s+({IDENT})\b"
)
MULTI_DECL_RE = re.compile(rf"(?m)^\s*(?:Axioms?|Parameters?)\s+([^:\n]+?)\s*:")
IDENT_RE = re.compile(IDENT)


def strip_coq_comments(source: str) -> str:
    output: list[str] = []
    depth = 0
    index = 0
    while index < len(source):
        pair = source[index:index + 2]
        if pair == "(*":
            depth += 1
            index += 2
            continue
        if pair == "*)" and depth:
            depth -= 1
            index += 2
            continue
        if depth == 0:
            output.append(source[index])
        index += 1
    if depth:
        raise ValueError("unterminated Coq comment")
    return "".join(output)


def extract_explicit_declarations(source: str) -> list[str]:
    stripped = strip_coq_comments(source)
    names = SINGLE_DECL_RE.findall(stripped)
    for names_blob in MULTI_DECL_RE.findall(stripped):
        names.extend(IDENT_RE.findall(names_blob))
    if len(names) != len(set(names)):
        duplicates = sorted({name for name in names if names.count(name) > 1})
        raise ValueError(f"duplicate explicit declaration: {', '.join(duplicates)}")
    return sorted(names)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest(formal_root: Path) -> dict:
    formal_root = formal_root.resolve()
    files: dict[str, dict[str, object]] = {}
    for source in sorted(formal_root.rglob("*.v")):
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"invalid Coq source: {source}")
        relative = source.relative_to(formal_root).as_posix()
        raw = source.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Coq source is not UTF-8: {relative}") from exc
        files[relative] = {
            "declarations": extract_explicit_declarations(text),
            "source_sha256": _sha256(raw),
        }
    if not files:
        raise ValueError("no Coq sources found")
    return {
        "binding_scope": BINDING_SCOPE,
        "files": files,
        "kind": KIND,
    }


def manifest_bytes(manifest: dict) -> bytes:
    return (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def verify_committed_manifest(formal_root: Path, manifest_path: Path) -> dict:
    expected = manifest_bytes(build_manifest(formal_root))
    actual = manifest_path.read_bytes()
    if actual != expected:
        raise ValueError("committed Coq target manifest drift")
    value = json.loads(actual.decode("utf-8"))
    if value.get("kind") != KIND or value.get("binding_scope") != BINDING_SCOPE:
        raise ValueError("unsupported Coq target manifest")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            verify_committed_manifest(args.formal_root, args.out)
        else:
            data = manifest_bytes(build_manifest(args.formal_root))
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(data)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Coq target census failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
