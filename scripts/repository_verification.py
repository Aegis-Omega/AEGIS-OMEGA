#!/usr/bin/env python3
"""Create deterministic repository-wide verification evidence.

The collector keeps static definitions, executed tests, and exclusions separate.
A source-pattern count is never represented as a passing-test count.
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
RESULT_KIND = "AEGIS_VERIFICATION_SUITE_RESULT_V1"
CENSUS_KIND = "AEGIS_TEST_DEFINITION_CENSUS_V1"
RECEIPT_KIND = "AEGIS_REPOSITORY_VERIFICATION_RECEIPT_V1"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, timeout=120, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def identity() -> tuple[str, str]:
    return git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")


def tracked(pattern: str) -> list[Path]:
    output = git("ls-files", pattern)
    return [Path(line) for line in output.splitlines() if line]


def count_definitions(paths: Iterable[Path], pattern: re.Pattern[str]) -> tuple[int, int]:
    count = files = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        files += 1
        count += sum(bool(pattern.search(line)) for line in text.splitlines())
    return count, files


def build_census(exclusions: list[dict[str, str]]) -> dict[str, Any]:
    rust, rust_files = count_definitions(
        tracked("*.rs"), re.compile(r"^\s*#\[(?:tokio::)?test\]")
    )
    typescript, ts_files = count_definitions(
        tracked("*.ts") + tracked("*.tsx"), re.compile(r"^\s*(?:it|test)\s*\(")
    )
    python, py_files = count_definitions(
        tracked("*.py"), re.compile(r"^\s*def\s+test_[A-Za-z0-9_]*\s*\(")
    )
    commit, tree = identity()
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": CENSUS_KIND,
        "repository": os.getenv("GITHUB_REPOSITORY", "Aegis-Omega/AEGIS-OMEGA"),
        "commit_sha": commit,
        "tree_sha": tree,
        "definition_counts": {
            "python": {"definitions": python, "files_scanned": py_files},
            "rust": {"definitions": rust, "files_scanned": rust_files},
            "typescript": {"definitions": typescript, "files_scanned": ts_files},
        },
        "definition_total": rust + typescript + python,
        "exclusions": sorted(exclusions, key=lambda item: item["path"]),
        "warning": "Static definitions are not executed-test evidence.",
    }
    body["census_digest"] = digest(body)
    return body


def clean(log: str) -> str:
    return ANSI.sub("", log).replace("\r", "")


def parse_cargo(log: str) -> tuple[int | None, int | None]:
    matches = re.findall(
        r"test result:\s+(?:ok|FAILED)\.\s+(\d+) passed;\s+(\d+) failed;\s+(\d+) ignored",
        clean(log),
    )
    if not matches:
        return None, None
    return sum(int(row[0]) for row in matches), sum(int(row[2]) for row in matches)


def parse_vitest(log: str) -> tuple[int | None, int | None]:
    matches = re.findall(
        r"\bTests\s+(\d+)\s+passed(?:\s*\|\s*(\d+)\s+skipped)?",
        clean(log),
    )
    if not matches:
        return None, None
    passed, skipped = matches[-1]
    return int(passed), int(skipped or 0)


def parse_pytest(log: str) -> tuple[int | None, int | None]:
    matches = re.findall(
        r"(?:^|\s)(\d+) passed(?:,\s*(\d+) skipped)?", clean(log), re.MULTILINE
    )
    if not matches:
        return None, None
    passed, skipped = matches[-1]
    return int(passed), int(skipped or 0)


def parse_unittest(log: str) -> tuple[int | None, int | None]:
    matches = re.findall(r"Ran\s+(\d+)\s+tests?", clean(log))
    return (int(matches[-1]), 0) if matches else (None, None)


def parse_log(parser: str, log: str) -> tuple[int | None, int | None]:
    functions = {
        "cargo": parse_cargo,
        "pytest": parse_pytest,
        "unittest": parse_unittest,
        "vitest": parse_vitest,
        "none": lambda _: (None, None),
    }
    return functions[parser](log)


def build_result(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.log)
    log = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    passed, skipped = parse_log(args.parser, log)
    commit, tree = identity()
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": RESULT_KIND,
        "suite_id": args.suite_id,
        "classification": args.classification,
        "status": "PASSED" if args.exit_code == 0 else "FAILED",
        "exit_code": args.exit_code,
        "command": args.suite_command,
        "parser": args.parser,
        "executed_tests": passed,
        "skipped_tests": skipped,
        "commit_sha": commit,
        "tree_sha": tree,
        "log_sha256": hashlib.sha256(log.encode("utf-8")).hexdigest(),
    }
    body["result_digest"] = digest(body)
    return body


def read_documents(root: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            documents.append(value)
    return documents


def aggregate(root: Path, required: Sequence[str]) -> tuple[dict[str, Any], str]:
    documents = read_documents(root)
    census = next((item for item in documents if item.get("artifact_kind") == CENSUS_KIND), None)
    results = [item for item in documents if item.get("artifact_kind") == RESULT_KIND]
    by_id = {str(item.get("suite_id")): item for item in results}
    missing = sorted(set(required) - set(by_id))
    failed = sorted(key for key, item in by_id.items() if item.get("status") != "PASSED")
    commits = sorted({str(item.get("commit_sha")) for item in results})
    trees = sorted({str(item.get("tree_sha")) for item in results})
    identity_valid = len(commits) == 1 and len(trees) == 1
    parsed = [item for item in results if isinstance(item.get("executed_tests"), int)]
    complete = census is not None and not missing and not failed and identity_valid
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": RECEIPT_KIND,
        "epistemic_status": "EXECUTION_EVIDENCE",
        "repository": os.getenv("GITHUB_REPOSITORY", "Aegis-Omega/AEGIS-OMEGA"),
        "commit_sha": commits[0] if identity_valid else None,
        "tree_sha": trees[0] if identity_valid else None,
        "status": "VERIFIED" if complete else "INCOMPLETE_OR_FAILED",
        "required_suites": sorted(required),
        "observed_suites": sorted(by_id),
        "missing_suites": missing,
        "failed_suites": failed,
        "executed_test_total_known": sum(int(item["executed_tests"]) for item in parsed),
        "skipped_test_total_known": sum(int(item.get("skipped_tests") or 0) for item in parsed),
        "suites_with_unparsed_assertion_count": sorted(
            str(item.get("suite_id")) for item in results if item.get("executed_tests") is None
        ),
        "definition_census": census,
        "suite_results": sorted(results, key=lambda item: str(item.get("suite_id"))),
        "authority_boundary": {
            "grants_runtime_authority": False,
            "proves_deployment_state": False,
            "proves_only_named_commands_at_commit": True,
        },
    }
    body["receipt_digest"] = digest(body)
    lines = [
        "# AEGIS Repository Verification Receipt",
        "",
        f"- Status: **{body['status']}**",
        f"- Commit: `{body['commit_sha']}`",
        f"- Executed tests with parsed counts: **{body['executed_test_total_known']}**",
        f"- Skipped tests with parsed counts: **{body['skipped_test_total_known']}**",
        f"- Static definitions found: **{census.get('definition_total') if census else 'MISSING'}**",
        f"- Receipt digest: `{body['receipt_digest']}`",
        "",
        "| Suite | Status | Executed | Skipped |",
        "|---|---:|---:|---:|",
    ]
    for item in body["suite_results"]:
        lines.append(
            f"| `{item['suite_id']}` | {item['status']} | "
            f"{item['executed_tests'] if item['executed_tests'] is not None else 'UNPARSED'} | "
            f"{item['skipped_tests'] if item['skipped_tests'] is not None else 'UNPARSED'} |"
        )
    if missing:
        lines += ["", f"Missing suites: `{', '.join(missing)}`"]
    if failed:
        lines += ["", f"Failed suites: `{', '.join(failed)}`"]
    lines += [
        "",
        "> This receipt reports named commands at one exact commit. Static definitions, "
        "unparsed contract assertions, exclusions, deployment state, and runtime authority remain separate.",
        "",
    ]
    return body, "\n".join(lines)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    census = commands.add_parser("census")
    census.add_argument("--output", required=True)
    census.add_argument("--exclusion", action="append", default=[])
    record = commands.add_parser("record")
    record.add_argument("--suite-id", required=True)
    record.add_argument("--suite-command", required=True)
    record.add_argument("--parser", choices=["cargo", "pytest", "unittest", "vitest", "none"], required=True)
    record.add_argument("--log", required=True)
    record.add_argument("--exit-code", type=int, required=True)
    record.add_argument("--classification", required=True)
    record.add_argument("--output", required=True)
    final = commands.add_parser("aggregate")
    final.add_argument("--input-dir", required=True)
    final.add_argument("--required-suite", action="append", default=[])
    final.add_argument("--json-output", required=True)
    final.add_argument("--markdown-output", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = arguments(argv or sys.argv[1:])
    if args.command == "census":
        exclusions = []
        for raw in args.exclusion:
            path, separator, reason = raw.partition("=")
            if not separator or not path or not reason:
                raise ValueError("--exclusion requires path=reason")
            exclusions.append({"path": path, "reason": reason})
        write_json(Path(args.output), build_census(exclusions))
        return 0
    if args.command == "record":
        write_json(Path(args.output), build_result(args))
        return 0
    receipt, markdown = aggregate(Path(args.input_dir), args.required_suite)
    write_json(Path(args.json_output), receipt)
    Path(args.markdown_output).write_text(markdown, encoding="utf-8")
    return 0 if receipt["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
