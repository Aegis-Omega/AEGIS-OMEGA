#!/usr/bin/env python3
"""Deterministic, non-mutating CLI for Cognitive Recovery Admission V1.

Exit status 0 means the verifier completed and emitted a receipt. It does not
mean recovery authority was granted. Admission outcome and authority are carried
only by the receipt. Input failures emit no receipt and return status 2.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR_PATH = SCRIPT_DIR / "validate-cognitive-recovery-admission.py"


class CliInputError(ValueError):
    """Deterministic fail-closed input error."""


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "aegis_cognitive_recovery_admission_validator", VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("VALIDATOR_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CliInputError(f"{label}_UNREADABLE_OR_INVALID") from exc
    if not isinstance(value, dict):
        raise CliInputError(f"{label}_NOT_OBJECT")
    return value


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate one offline cognitive-recovery admission request."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--recovery-evidence", required=True)
    parser.add_argument("--platform-observation", required=True)
    parser.add_argument("--operator-approval", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        repo = Path(args.repo)
        if not repo.is_dir() or not (repo / ".git").exists():
            raise CliInputError("REPO_UNAVAILABLE")

        request = _load_json_object(Path(args.request), "REQUEST")
        recovery_evidence = _load_json_object(
            Path(args.recovery_evidence), "RECOVERY_EVIDENCE"
        )
        platform_observation = _load_json_object(
            Path(args.platform_observation), "PLATFORM_OBSERVATION"
        )
        operator_approval = _load_json_object(
            Path(args.operator_approval), "OPERATOR_APPROVAL"
        )
    except CliInputError as exc:
        sys.stderr.write(f"INPUT_ERROR: {exc}\n")
        return 2

    try:
        validator = _load_validator()
        verifier_code_digest = hashlib.sha256(VALIDATOR_PATH.read_bytes()).hexdigest()
        receipt = validator.evaluate(
            repo=repo,
            request=request,
            recovery_evidence=recovery_evidence,
            platform_observation=platform_observation,
            operator_approval=operator_approval,
            verifier_code_digest=verifier_code_digest,
        )
        output = validator.canonical_bytes(receipt).decode("utf-8")
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        # Internal verification errors never emit a partial receipt. Keep stderr
        # deterministic instead of leaking environment-specific paths/details.
        del exc
        sys.stderr.write("VERIFIER_ERROR: EVALUATION_FAILED\n")
        return 3

    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
