#!/usr/bin/env python3
"""Build deterministic repository-wide verification evidence.

This utility keeps three quantities separate:

1. test definitions found in tracked source;
2. tests actually executed by a named runner;
3. exclusions or skips with an explicit reason.

A static definition count is never reported as a passing-test count.
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
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = "1.0.0"
RECEIPT_KIND = "AEGIS_REPOSITORY_VERIFICATION_RECEIPT_V1"
RESULT_KIND = "AEGIS_VERIFICATION_SUITE_RESULT_V1"
CENSUS_KIND = "AEGIS_TEST_DEFINITION_CENSUS_V1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False, timeout=120
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def tracked_files(patterns: Iterable[str]) -> list[Path]:
    output = git("ls-files", *patterns)
    return [Path(line) for line in output.splitlines() if line.strip()]


def count_matches(paths: Iterable[Path], expression: re.Pattern[str]) -> tuple[int, int]:
    definitions = 0
    readable_files = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError):
            continue
        readable_files += 1
        definitions += sum(1 for line in text.splitlines() if expression.search(line))
    return definitions, readable_files


def build_census(exclusions: list[dict[str, str]]) -> dict[str, Any]:
    rust_count, rust_files = count_matches(
        tracked_files(["*.rs"]), re.compile(r"^\s*#\[(?:tokio::)?test\]")
    )
    ts_count, ts_files = count_matches(
        tracked_files(["*.ts", "*.tsx"]), re.compile(r"^\s*(?:it|test)\s*\(")
    )
    py_count, py_files = count_matches(
        tracked_files(["*.py"]), re.compile(r"^\s*def\s+test_[A-Za-z0-9_]*\s*\(")
    )
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": CENSUS_KIND,
        "repository": os.environ.get("GITHUB_REPOSITORY", "Aegis-Omega/AEGIS-OMEGA"),
        "commit_sha": git("rev-parse", "HEAD"),
        "tree_sha": git("rev-parse", "HEAD^{tree}"),
        "definition_counts": {
            "python": {"definitions": py_count, "files_scanned": py_files},
            "rust": {"definitions": rust_count, "files_scanned": rust_files},
            "typescript": {"definitions": ts_count, "files_scanned": ts_files},
        },
        "definition_total": rust_count + ts_count + py_count,
        "exclusions": exclusions,
        "warning": "Definition census is static source evidence, not executed-test evidence.",
    }
    body["census_digest"] = sha256_text(canonical_json(body))
    return body


def parse_cargo(log: str) -> tuple[int | None, int | None]:
    matches = re.findall(
        r"test result:\s+(?:ok|FAILED)\.\s+(\d+) passed;\s+(\d+) failed;\s+(\d+) ignored",
        log,
    )
    if not matches:
        return None, None
    passed = sum(int(item[0]) for item in matches)
    skipped = sum(int(item[2]) for item in matches)
    return passed, skipped


def parse_vitest(log: str) -> tuple[int | None, int | None]:
    passed_matches = re.findall(r"Tests\s+(\d+) passed", log)
    skipped_matches = re.findall(r"(?:\||,)\s*(\d+) skipped", log)
    if not passed_matches:
        return None, None
    return int(passed_matches[-1]), int(skipped_matches[-1]) if skipped_matches else 0


def parse_pytest(log: str) -> tuple[int | None, int | None]:
    matches = re.findall(r"(?:^|\s)(\d+) passed(?:,\s*(\d+) skipped)?", log)
    if not matches:
        return None, None
    passed, skipped = matches[-1]
    return int(passed), int(skipped or 0)


def parse_unittest(log: str) -> tuple[int | None, int | None]:
    matches = re.findall(r"Ran\s+(\d+)\s+tests?", log)
    if not matches:
        return None, None
    return int(matches[-1]), 0


def parse_log(parser_name: str, log: str) -> tuple[int | None, int | None]:
    parsers = {
        "cargo": parse_cargo,
        "pytest": parse_pytest,
        "unittest": parse_unittest,
        "vitest": parse_vitest,
        "none": lambda _log: (None, None),
    }
    try:
        parser = parsers[parser_name]
    except KeyError as exc:
        raise ValueError(f"unsupported parser: {parser_name}") from exc
    return parser(log)


def build_suite_result(
    *,
    suite_id: str,
    command: str,
    parser_name: str,
    log_path: Path,
    exit_code: int,
    classification: str,
) -> dict[str, Any]:
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    passed, skipped = parse_log(parser_name, log)
    status = "PASSED" if exit_code == 0 else "FAILED"
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": RESULT_KIND,
        "suite_id": suite_id,
        "classification": classification,
        "status": status,
        "exit_code": exit_code,
        "command": command,
        "parser": parser_name,
        "executed_tests": passed,
        "skipped_tests": skipped,
        "commit_sha": git("rev-parse", "HEAD"),
        "tree_sha": git("rev-parse", "HEAD^{tree}"),
        "log_sha256": hashlib.sha256(log.encode("utf-8")).hexdigest(),
    }
    body["result_digest"] = sha256_text(canonical_json(body))
    return body


def load_json_files(root: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            documents.append(value)
    return documents


def build_receipt(input_dir: Path, required_suites: Sequence[str]) -> tuple[dict[str, Any], str]:
    documents = load_json_files(input_dir)
    census = next((doc for doc in documents if doc.get("artifact_kind") == CENSUS_KIND), None)
    results = [doc for doc in documents if doc.get("artifact_kind") == RESULT_KIND]
    by_id = {str(result.get("suite_id")): result for result in results}
    missing = sorted(set(required_suites) - set(by_id))
    failed = sorted(
        suite_id for suite_id, result in by_id.items() if result.get("status") != "PASSED"
    )
    known_counts = [
        int(result["executed_tests"])
        for result in results
        if isinstance(result.get("executed_tests"), int)
    ]
    known_skips = [
        int(result["skipped_tests"])
        for result in results
        if isinstance(result.get("skipped_tests"), int)
    ]
    commit_values = sorted({str(result.get("commit_sha")) for result in results})
    tree_values = sorted({str(result.get("tree_sha")) for result in results})
    complete = not missing and not failed and len(commit_values) == 1 and len(tree_values) == 1
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": RECEIPT_KIND,
        "epistemic_status": "EXECUTION_EVIDENCE",
        "repository": os.environ.get("GITHUB_REPOSITORY", "Aegis-Omega/AEGIS-OMEGA"),
        "commit_sha": commit_values[0] if len(commit_values) == 1 else None,
        "tree_sha": tree_values[0] if len(tree_values) == 1 else None,
        "status": "VERIFIED" if complete else "INCOMPLETE_OR_FAILED",
        "required_suites": sorted(required_suites),
        "observed_suites": sorted(by_id),
        "missing_suites": missing,
        "failed_suites": failed,
        "executed_test_total_known": sum(known_counts),
        "skipped_test_total_known": sum(known_skips),
        "suites_with_unparsed_assertion_count": sorted(
            str(result.get("suite_id"))
            for result in results
            if result.get("executed_tests") is None
        ),
        "definition_census": census,
        "suite_results": sorted(results, key=lambda item: str(item.get("suite_id"))),
        "authority_boundary": {
            "grants_runtime_authority": False,
            "proves_deployment_state": False,
            "proves_only_named_commands_at_commit": True,
        },
    }
    body["receipt_digest"] = sha256_text(canonical_json(body))
    lines = [
        "# AEGIS Repository Verification Receipt",
        "",
        f"- Status: **{body['status']}**",
        f"- Commit: `{body['commit_sha']}`",
        f"- Executed tests with parsed counts: **{body['executed_test_total_known']}**",
        f"- Skipped tests with parsed counts: **{body['skipped_test_total_known']}**",
        f"- Static definitions found: **{census.get('definition_total') if census else 'missing'}**",
        f"- Receipt digest: `{body['receipt_digest']}`",
        "",
        "| Suite | Status | Executed | Skipped |",
        "|---|---:|---:|---:|",
    ]
    for result in body["suite_results"]:
        lines.append(
            f"| `{result['suite_id']}` | {result['status']} | "
            f"{result['executed_tests'] if result['executed_tests'] is not None else 'UNPARSED'} | "
            f"{result['skipped_tests'] if result['skipped_tests'] is not None else 'UNPARSED'} |"
        )
    if missing:
        lines += ["", f"Missing suites: `{', '.join(missing)}`"]
    if failed:
        lines += ["", f"Failed suites: `{', '.join(failed)}`"]
    lines += [
        "",
        "> This receipt does not claim that every static test definition was executed. "
        "It reports only named commands and explicitly identifies unparsed or excluded surfaces.",
        "",
    ]
    return body, "\n".join(lines)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    census = sub.add_parser("census")
    census.add_argument("--output", required=True)
    census.add_argument("--exclusion", action="append", default=[])

    record = sub.add_parser("record")
    record.add_argument("--suite-id", required=True)
    record.add_argument("--suite-command", required=True)
    record.add_argument("--parser", choices=["cargo", "pytest", "unittest", "vitest", "none"], required=True)
    record.add_argument("--log", required=True)
    record.add_argument("--exit-code", required=True, type=int)
    record.add_argument("--classification", default="TEST_EXECUTION")
    record.add_argument("--output", required=True)

    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--input-dir", required=True)
    aggregate.add_argument("--required-suite", action="append", default=[])
    aggregate.add_argument("--json-output", required=True)
    aggregate.add_argument("--markdown-output", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.command == "census":
        exclusions = []
        for item in args.exclusion:
            path, separator, reason = item.partition("=")
            if not separator or not path or not reason:
                raise ValueError("--exclusion must use path=reason")
            exclusions.append({"path": path, "reason": reason})
        write_json(Path(args.output), build_census(exclusions))
        return 0
    if args.command == "record":
        result = build_suite_result(
            suite_id=args.suite_id,
            command=args.suite_command,
            parser_name=args.parser,
            log_path=Path(args.log),
            exit_code=args.exit_code,
            classification=args.classification,
        )
        write_json(Path(args.output), result)
        return 0
    if args.command == "aggregate":
        receipt, markdown = build_receipt(Path(args.input_dir), args.required_suite)
        write_json(Path(args.json_output), receipt)
        Path(args.markdown_output).write_text(markdown, encoding="utf-8")
        return 0 if receipt["status"] == "VERIFIED" else 1
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
