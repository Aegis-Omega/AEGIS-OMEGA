"""AEGIS System Foundry: local contract-test runner for one bounded system family.

Input is a typed blueprint, never arbitrary code. The compiler owns ALL executable
source and tests. A local subprocess proves function for a particular generated
candidate; it does not constitute a secure sandbox, supply remote attestation, or
grant Automaton-3 operational authority.

Usage:
  python -m harness.sdk.generator.foundry_runner --blueprint blueprint.json
  python -m harness.sdk.generator.foundry_runner --blueprint blueprint.json --output-dir /tmp/demo-app

Requires Python 3.11+; standard library only.
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
import tempfile
from typing import Any, Mapping

from harness.sdk.generator.system_foundry import build_readonly_json_api
from harness.sdk.generator import CodeArtifact

KIND = "AEGIS_SYSTEM_FOUNDRY_LOCAL_CONTRACT_RECEIPT_V1"
_ALLOWED_FILES = frozenset({"service.py", "test_service.py", "README.md"})
_RAN = re.compile(r"(?m)^Ran ([0-9]+) tests? in ")
_MAX_OUTPUT = 64_000


class LocalBuildError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _verify_artifacts(artifacts: list[CodeArtifact]) -> None:
    if not isinstance(artifacts, list) or len(artifacts) != len(_ALLOWED_FILES):
        raise LocalBuildError("ARTIFACT_SET_INVALID")
    if {a.path for a in artifacts} != _ALLOWED_FILES:
        raise LocalBuildError("ARTIFACT_PATH_SET_INVALID")
    for a in artifacts:
        if type(a.content) is not str or hashlib.sha256(
            a.content.encode("utf-8")
        ).hexdigest() != a.hash:
            raise LocalBuildError("ARTIFACT_HASH_MISMATCH")


def _write_artifacts(artifacts: list[CodeArtifact], directory: Path) -> None:
    _verify_artifacts(artifacts)
    for item in artifacts:
        # Fixed names owned by trusted compiler, never request-derived paths.
        (directory / item.path).write_text(item.content, encoding="utf-8")


def run_local_contract(
    blueprint: Mapping[str, Any], *, timeout_seconds: int = 10,
) -> dict[str, Any]:
    """Compile a trusted template and run its actual unit tests in a subprocess.

    This is a *local functional check*, NOT a security sandbox or positive
    admission decision. Never execute arbitrary user-provided source this way.
    """
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30:
        raise LocalBuildError("TEST_TIMEOUT_INVALID")
    artifacts = build_readonly_json_api(blueprint)
    _verify_artifacts(artifacts)

    with tempfile.TemporaryDirectory(prefix="aegis-foundry-") as tmp:
        root = Path(tmp)
        _write_artifacts(artifacts, root)
        try:
            proc = subprocess.run(
                [sys.executable, "-B", "-S", "test_service.py"],
                cwd=root,
                env={
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                },
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            rc = proc.returncode
            stdout = proc.stdout[:_MAX_OUTPUT]
            stderr = proc.stderr[:_MAX_OUTPUT]
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            rc = None
            stdout = (exc.stdout or b"")[:_MAX_OUTPUT]
            stderr = (exc.stderr or b"")[:_MAX_OUTPUT]
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", "replace")
            timed_out = True

    # The generated application's self-tests are not an acceptance oracle.
    # Run source-controlled acceptance logic from OUTSIDE generated artifacts.
    oracle_source = Path(__file__).resolve().with_name("independent_oracle.py")
    oracle_source_digest = hashlib.sha256(oracle_source.read_bytes()).hexdigest()
    oracle_result: dict[str, Any] = {}
    oracle_exit: int | None = None
    oracle_stdout = ""
    oracle_stderr = ""
    oracle_timeout = False
    with tempfile.TemporaryDirectory(prefix="aegis-foundry-oracle-") as tmp:
        oracle_root = Path(tmp)
        _write_artifacts(artifacts, oracle_root)
        blueprint_path = oracle_root / "blueprint.json"
        blueprint_path.write_bytes(_canonical(blueprint))
        try:
            oracle_proc = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(oracle_source),
                 str(blueprint_path), str(oracle_root / "service.py")],
                cwd=oracle_root,
                env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
            oracle_exit = oracle_proc.returncode
            oracle_stdout = oracle_proc.stdout[:_MAX_OUTPUT]
            oracle_stderr = oracle_proc.stderr[:_MAX_OUTPUT]
            try:
                oracle_result = json.loads(oracle_stdout)
            except (ValueError, TypeError):
                oracle_result = {}
        except subprocess.TimeoutExpired:
            oracle_timeout = True

    oracle_expected_sha = hashlib.sha256(
        next(a.content.encode("utf-8") for a in artifacts if a.path == "service.py")
    ).hexdigest()
    oracle_pass = bool(
        oracle_exit == 0
        and oracle_result.get("outcome") == "ORACLE_PASS"
        and oracle_result.get("service_sha256") == oracle_expected_sha
        and oracle_result.get("blueprint_sha256") == hashlib.sha256(_canonical(blueprint)).hexdigest()
        and type(oracle_result.get("total")) is int
        and oracle_result["total"] >= len(blueprint["routes"]) + 6
        and oracle_result.get("passed") == oracle_result["total"]
        and oracle_result.get("admission") == "NOT_ADMITTED"
        and oracle_result.get("authority_granted") is False
    )
    match = _RAN.search(stderr)
    tests_run = int(match.group(1)) if match else 0
    # Wall-clock durations and temporary directory names are observations,
    # never deterministic receipt input. Preserve a raw digest separately.
    normalized_stderr = re.sub(
        r"(?m)^Ran ([0-9]+) tests? in [0-9.]+s$",
        r"Ran \1 tests in [elapsed]s",
        stderr.replace(str(root), "<WORKSPACE>"),
    )
    # unittest outputs an independent completed OK line. This is not
    # cryptographic evidence, so admission remains NOT_ADMITTED even on PASS.
    passed = bool(
        rc == 0 and not timed_out and tests_run >= 3
        and re.search(r"(?m)^OK$", stderr) is not None
        and oracle_pass and not oracle_timeout
    )
    body: dict[str, Any] = {
        "schema_version": "1.0.0",
        "receipt_kind": KIND,
        "system_id": blueprint["system_id"],
        "blueprint_sha256": hashlib.sha256(_canonical(blueprint)).hexdigest(),
        "artifacts": {a.path: a.hash for a in sorted(artifacts, key=lambda a: a.path)},
        "runner": "LOCAL_PROCESS_NOT_A_SECURITY_SANDBOX",
        "outcome": "LOCAL_TEST_PASS" if passed else "LOCAL_TEST_FAIL",
        "test_count": tests_run,
        "exit_code": rc,
        "independent_oracle": {
            "source_sha256": oracle_source_digest,
            "report_sha256": hashlib.sha256(
                _canonical(oracle_result) if oracle_result else b""
            ).hexdigest(),
            "test_count": oracle_result.get("total", 0),
            "passed_count": oracle_result.get("passed", 0),
            "outcome": "ORACLE_PASS" if oracle_pass else "ORACLE_FAIL",
            "exit_code": oracle_exit,
            "timed_out": oracle_timeout,
        },
        "timed_out": timed_out,
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(normalized_stderr.encode("utf-8")).hexdigest(),
        "admission": "NOT_ADMITTED",
        "authority_granted": False,
    }
    receipt_sha256 = hashlib.sha256(
        _canonical({"domain": KIND, "receipt": body})
    ).hexdigest()
    return {
        **body,
        "receipt_sha256": receipt_sha256,
        # Not part of the deterministic receipt and not independently signed.
        "unattested_observation": {
            "stderr_raw_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        },
    }


def materialize_candidate(
    blueprint: Mapping[str, Any], output_dir: str | Path,
) -> list[CodeArtifact]:
    """Write compiler-owned source into a NEW folder only; never overwrite."""
    artifacts = build_readonly_json_api(blueprint)
    _verify_artifacts(artifacts)
    target = Path(output_dir)
    try:
        target.mkdir(parents=False, exist_ok=False)
    except OSError as exc:
        raise LocalBuildError("OUTPUT_DIRECTORY_MUST_NOT_EXIST") from exc
    _write_artifacts(artifacts, target)
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="AEGIS bounded system factory")
    parser.add_argument("--blueprint", required=True)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    try:
        blueprint = json.loads(Path(args.blueprint).read_text(encoding="utf-8"))
        receipt = run_local_contract(blueprint)
        if args.output_dir and receipt["outcome"] == "LOCAL_TEST_PASS":
            materialize_candidate(blueprint, args.output_dir)
    except (OSError, ValueError, TypeError) as exc:
        print("FOUNDRY_DENIED:" + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0 if receipt["outcome"] == "LOCAL_TEST_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
