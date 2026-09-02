#!/usr/bin/env python3
"""Trusted, read-only evaluator for cognitive-anchor admission.

This module is intended to execute only from a ruleset-owned workflow source.
Candidate repository content is treated strictly as data. The evaluator loads
its manifest generator from the same trusted source tree as this file, derives
expected anchors from the trusted base state, and admits only byte-identical
regeneration.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
ZERO_HASH = "0" * 64
MAX_SKILL_FILES = 4096
MAX_COGNITIVE_BYTES = 16 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 2 * 1024 * 1024


def _load_generator():
    path = Path(__file__).with_name("build-cognitive-manifest.py")
    spec = importlib.util.spec_from_file_location("trusted_cognitive_generator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load trusted generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _validate_sha(name: str, value: str) -> None:
    if SHA1_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase 40-hex commit SHA")


def _scan_untrusted_root(root: Path) -> list[str]:
    """Reject link/device tricks and bound cognitive input size before parsing."""
    violations: list[str] = []
    if not root.is_dir():
        return [f"missing repository root: {root}"]

    skill_count = 0
    cognitive_bytes = 0
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in list(dirnames) + list(filenames):
            path = current_path / name
            try:
                info = path.lstat()
            except OSError as exc:
                violations.append(f"cannot lstat {path.relative_to(root)}: {exc}")
                continue
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(info.st_mode):
                violations.append(f"symlink forbidden: {relative}")
                continue
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                violations.append(f"special file forbidden: {relative}")
                continue
            if stat.S_ISREG(info.st_mode) and info.st_size > MAX_SINGLE_FILE_BYTES:
                violations.append(f"file exceeds trusted parser bound: {relative}")

        for name in filenames:
            path = current_path / name
            try:
                info = path.lstat()
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            relative = path.relative_to(root).as_posix()
            is_cognitive = (
                name == "SKILL.md"
                or relative == ".claude.json"
                or relative == "skill-hashes.sha256"
            )
            if not is_cognitive:
                continue
            cognitive_bytes += info.st_size
            if name == "SKILL.md":
                skill_count += 1

    if skill_count > MAX_SKILL_FILES:
        violations.append(
            f"skill file count exceeds bound: {skill_count}>{MAX_SKILL_FILES}"
        )
    if cognitive_bytes > MAX_COGNITIVE_BYTES:
        violations.append(
            f"cognitive bytes exceed bound: {cognitive_bytes}>{MAX_COGNITIVE_BYTES}"
        )
    return violations


def _read_bytes(path: Path, violations: list[str]) -> bytes | None:
    try:
        info = path.lstat()
    except OSError as exc:
        violations.append(f"missing required file {path.name}: {exc}")
        return None
    if not stat.S_ISREG(info.st_mode):
        violations.append(f"required file is not regular: {path.name}")
        return None
    if info.st_size > MAX_SINGLE_FILE_BYTES:
        violations.append(f"required file exceeds bound: {path.name}")
        return None
    try:
        return path.read_bytes()
    except OSError as exc:
        violations.append(f"cannot read {path.name}: {exc}")
        return None


def _validate_base(generator, base_root: Path, violations: list[str]) -> tuple[str | None, dict[str, Any] | None]:
    manifest_bytes = _read_bytes(base_root / ".claude.json", violations)
    hashes_bytes = _read_bytes(base_root / "skill-hashes.sha256", violations)
    if manifest_bytes is None or hashes_bytes is None:
        return None, None

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        generator.validate_manifest(manifest)
    except Exception as exc:  # fail closed on any malformed trusted-base claim
        violations.append(f"base manifest invalid: {exc}")
        return None, None

    state_hash = manifest.get("state_hash")
    if not isinstance(state_hash, str) or state_hash == ZERO_HASH:
        violations.append("base state hash must be nonzero")
        return None, manifest

    provenance = manifest.get("provenance", {})
    parent_state_hash = provenance.get("parent_state_hash")
    source_ref = provenance.get("source_ref")
    if not isinstance(parent_state_hash, str) or not isinstance(source_ref, str):
        violations.append("base provenance missing source_ref/parent_state_hash")
        return None, manifest

    try:
        expected_manifest, expected_hashes = generator.build_manifest(
            base_root,
            source_ref=source_ref,
            parent_state_hash=parent_state_hash,
        )
        expected_manifest_bytes = generator.render_manifest(expected_manifest).encode("utf-8")
        expected_hashes_bytes = expected_hashes.encode("utf-8")
    except Exception as exc:
        violations.append(f"base regeneration failed: {exc}")
        return None, manifest

    if manifest_bytes != expected_manifest_bytes:
        violations.append("base manifest is not exact trusted regeneration")
    if hashes_bytes != expected_hashes_bytes:
        violations.append("base skill hash ledger is not exact trusted regeneration")
    return state_hash, manifest


def evaluate(
    *,
    candidate_root: Path,
    base_root: Path,
    source_ref: str,
    candidate_sha: str,
    base_sha: str,
    workflow_sha: str,
) -> dict[str, Any]:
    """Return an immutable-style receipt; outcome is ADMITTED only on exact match."""
    _validate_sha("candidate_sha", candidate_sha)
    _validate_sha("base_sha", base_sha)
    _validate_sha("workflow_sha", workflow_sha)
    if not source_ref or source_ref.startswith("-"):
        raise ValueError("source_ref must be a non-empty branch ref")

    candidate_root = Path(candidate_root).resolve()
    base_root = Path(base_root).resolve()
    generator = _load_generator()
    violations: list[str] = []
    violations.extend(_scan_untrusted_root(base_root))
    violations.extend(_scan_untrusted_root(candidate_root))

    base_state_hash, _ = _validate_base(generator, base_root, violations)
    expected_manifest_bytes: bytes | None = None
    expected_hashes_bytes: bytes | None = None
    if base_state_hash is not None:
        try:
            expected_manifest, expected_hashes = generator.build_manifest(
                candidate_root,
                source_ref=source_ref,
                parent_state_hash=base_state_hash,
            )
            expected_manifest_bytes = generator.render_manifest(expected_manifest).encode("utf-8")
            expected_hashes_bytes = expected_hashes.encode("utf-8")
        except Exception as exc:
            violations.append(f"candidate regeneration failed: {exc}")

    actual_manifest_bytes = _read_bytes(candidate_root / ".claude.json", violations)
    actual_hashes_bytes = _read_bytes(candidate_root / "skill-hashes.sha256", violations)
    if expected_manifest_bytes is not None and actual_manifest_bytes is not None:
        if actual_manifest_bytes != expected_manifest_bytes:
            violations.append("candidate manifest differs from trusted regeneration")
    if expected_hashes_bytes is not None and actual_hashes_bytes is not None:
        if actual_hashes_bytes != expected_hashes_bytes:
            violations.append("candidate skill hash ledger differs from trusted regeneration")

    receipt: dict[str, Any] = {
        "schema": "aegis.trusted-cognitive-admission.v1",
        "outcome": "ADMITTED" if not violations else "DENIED",
        "candidate_sha": candidate_sha,
        "base_sha": base_sha,
        "workflow_sha": workflow_sha,
        "source_ref": source_ref,
        "base_state_hash": base_state_hash,
        "trusted_generator_sha256": _sha256(
            Path(generator.__file__).read_bytes()
        ),
        "trusted_evaluator_sha256": _sha256(Path(__file__).read_bytes()),
        "actual_candidate_manifest_sha256": (
            _sha256(actual_manifest_bytes) if actual_manifest_bytes is not None else None
        ),
        "expected_candidate_manifest_sha256": (
            _sha256(expected_manifest_bytes) if expected_manifest_bytes is not None else None
        ),
        "actual_skill_ledger_sha256": (
            _sha256(actual_hashes_bytes) if actual_hashes_bytes is not None else None
        ),
        "expected_skill_ledger_sha256": (
            _sha256(expected_hashes_bytes) if expected_hashes_bytes is not None else None
        ),
        "violation_count": len(violations),
        "violations": violations,
    }
    receipt["receipt_sha256"] = _sha256(_canonical(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--base-root", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        receipt = evaluate(
            candidate_root=Path(args.candidate_root),
            base_root=Path(args.base_root),
            source_ref=args.source_ref,
            candidate_sha=args.candidate_sha,
            base_sha=args.base_sha,
            workflow_sha=args.workflow_sha,
        )
    except Exception as exc:
        receipt = {
            "schema": "aegis.trusted-cognitive-admission.v1",
            "outcome": "DENIED",
            "candidate_sha": args.candidate_sha,
            "base_sha": args.base_sha,
            "workflow_sha": args.workflow_sha,
            "source_ref": args.source_ref,
            "violation_count": 1,
            "violations": [f"trusted evaluator exception: {type(exc).__name__}: {exc}"],
        }
        receipt["receipt_sha256"] = _sha256(_canonical(receipt))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"TRUSTED_COGNITIVE_ADMISSION {receipt['outcome']} {receipt['receipt_sha256']}")
    for violation in receipt.get("violations", []):
        print(f"DENIAL: {violation}")
    return 0 if receipt["outcome"] == "ADMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
