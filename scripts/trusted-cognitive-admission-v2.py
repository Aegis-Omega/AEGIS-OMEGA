#!/usr/bin/env python3
"""Trusted cognitive admission v2.

Manifest authority is semantic and hash-bound, not whitespace-bound. This
revision preserves the v1 filesystem safety/bounds and exact skill-ledger
checks, while comparing validated manifests through canonical JSON content.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_v1():
    path = Path(__file__).with_name("trusted-cognitive-admission.py")
    spec = importlib.util.spec_from_file_location("trusted_cognitive_admission_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load trusted evaluator v1: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V1 = _load_v1()
ZERO_HASH = V1.ZERO_HASH


def _read_manifest(
    generator: Any,
    root: Path,
    label: str,
    violations: list[str],
) -> tuple[dict[str, Any] | None, bytes | None]:
    raw = V1._read_bytes(root / ".claude.json", violations)
    if raw is None:
        return None, None
    try:
        manifest = json.loads(raw.decode("utf-8"))
        generator.validate_manifest(manifest)
    except Exception as exc:
        violations.append(f"{label} manifest invalid: {exc}")
        return None, raw
    return manifest, raw


def _canonical_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return V1._canonical(left) == V1._canonical(right)


def evaluate(
    *,
    candidate_root: Path,
    base_root: Path,
    source_ref: str,
    candidate_sha: str,
    base_sha: str,
    workflow_sha: str,
) -> dict[str, Any]:
    V1._validate_sha("candidate_sha", candidate_sha)
    V1._validate_sha("base_sha", base_sha)
    V1._validate_sha("workflow_sha", workflow_sha)
    if not source_ref or source_ref.startswith("-"):
        raise ValueError("source_ref must be a non-empty branch ref")

    candidate_root = Path(candidate_root).resolve()
    base_root = Path(base_root).resolve()
    generator = V1._load_generator()
    violations: list[str] = []
    violations.extend(V1._scan_untrusted_root(base_root))
    violations.extend(V1._scan_untrusted_root(candidate_root))

    base_manifest, base_manifest_raw = _read_manifest(
        generator, base_root, "base", violations
    )
    base_hashes_raw = V1._read_bytes(base_root / "skill-hashes.sha256", violations)

    base_state_hash: str | None = None
    expected_base_manifest: dict[str, Any] | None = None
    expected_base_hashes_raw: bytes | None = None
    if base_manifest is not None:
        state_hash = base_manifest.get("state_hash")
        provenance = base_manifest.get("provenance", {})
        parent_state_hash = provenance.get("parent_state_hash")
        base_source_ref = provenance.get("source_ref")
        if not isinstance(state_hash, str) or state_hash == ZERO_HASH:
            violations.append("base state hash must be nonzero")
        elif not isinstance(parent_state_hash, str) or not isinstance(base_source_ref, str):
            violations.append("base provenance missing source_ref/parent_state_hash")
        else:
            base_state_hash = state_hash
            try:
                expected_base_manifest, expected_base_hashes = generator.build_manifest(
                    base_root,
                    source_ref=base_source_ref,
                    parent_state_hash=parent_state_hash,
                )
                expected_base_hashes_raw = expected_base_hashes.encode("utf-8")
            except Exception as exc:
                violations.append(f"base regeneration failed: {exc}")

    if base_manifest is not None and expected_base_manifest is not None:
        if not _canonical_equal(base_manifest, expected_base_manifest):
            violations.append("base manifest canonical content differs from trusted regeneration")
    if base_hashes_raw is not None and expected_base_hashes_raw is not None:
        if base_hashes_raw != expected_base_hashes_raw:
            violations.append("base skill hash ledger is not exact trusted regeneration")

    expected_candidate_manifest: dict[str, Any] | None = None
    expected_candidate_hashes_raw: bytes | None = None
    if base_state_hash is not None:
        try:
            expected_candidate_manifest, expected_candidate_hashes = generator.build_manifest(
                candidate_root,
                source_ref=source_ref,
                parent_state_hash=base_state_hash,
            )
            expected_candidate_hashes_raw = expected_candidate_hashes.encode("utf-8")
        except Exception as exc:
            violations.append(f"candidate regeneration failed: {exc}")

    candidate_manifest, candidate_manifest_raw = _read_manifest(
        generator, candidate_root, "candidate", violations
    )
    candidate_hashes_raw = V1._read_bytes(
        candidate_root / "skill-hashes.sha256", violations
    )

    if candidate_manifest is not None and expected_candidate_manifest is not None:
        if not _canonical_equal(candidate_manifest, expected_candidate_manifest):
            violations.append("candidate manifest canonical content differs from trusted regeneration")
    if candidate_hashes_raw is not None and expected_candidate_hashes_raw is not None:
        if candidate_hashes_raw != expected_candidate_hashes_raw:
            violations.append("candidate skill hash ledger differs from trusted regeneration")

    receipt: dict[str, Any] = {
        "schema": "aegis.trusted-cognitive-admission.v2",
        "outcome": "ADMITTED" if not violations else "DENIED",
        "candidate_sha": candidate_sha,
        "base_sha": base_sha,
        "workflow_sha": workflow_sha,
        "source_ref": source_ref,
        "base_state_hash": base_state_hash,
        "comparison_mode": "canonical-json-manifest+byte-exact-skill-ledger",
        "trusted_generator_sha256": V1._sha256(Path(generator.__file__).read_bytes()),
        "trusted_evaluator_sha256": V1._sha256(Path(__file__).read_bytes()),
        "actual_base_manifest_sha256": (
            V1._sha256(base_manifest_raw) if base_manifest_raw is not None else None
        ),
        "actual_candidate_manifest_sha256": (
            V1._sha256(candidate_manifest_raw) if candidate_manifest_raw is not None else None
        ),
        "expected_candidate_manifest_canonical_sha256": (
            V1._sha256(V1._canonical(expected_candidate_manifest))
            if expected_candidate_manifest is not None
            else None
        ),
        "actual_candidate_manifest_canonical_sha256": (
            V1._sha256(V1._canonical(candidate_manifest))
            if candidate_manifest is not None
            else None
        ),
        "actual_skill_ledger_sha256": (
            V1._sha256(candidate_hashes_raw) if candidate_hashes_raw is not None else None
        ),
        "expected_skill_ledger_sha256": (
            V1._sha256(expected_candidate_hashes_raw)
            if expected_candidate_hashes_raw is not None
            else None
        ),
        "violation_count": len(violations),
        "violations": violations,
    }
    receipt["receipt_sha256"] = V1._sha256(V1._canonical(receipt))
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
            "schema": "aegis.trusted-cognitive-admission.v2",
            "outcome": "DENIED",
            "candidate_sha": args.candidate_sha,
            "base_sha": args.base_sha,
            "workflow_sha": args.workflow_sha,
            "source_ref": args.source_ref,
            "violation_count": 1,
            "violations": [f"trusted evaluator exception: {type(exc).__name__}: {exc}"],
        }
        receipt["receipt_sha256"] = V1._sha256(V1._canonical(receipt))

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
