#!/usr/bin/env python3
"""AEGIS repository governance lint.

This checker enforces the quarantine boundary for the historical Gemma-Holon
quantum demonstrator. It is deliberately narrow: runtime code under
`sovereign-omega-v2/src/**` must never import/require the legacy
`clients/gemma-holon/**` surface, while orchestration/documentation outside
that source tree is not affected by this rule.

Exit semantics are fail-closed: any violation or unreadable candidate source
returns a non-zero exit status.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import NamedTuple, Sequence


LEGACY_RUNTIME_PATH = Path("clients/gemma-holon/quantum/server.py")
QUARANTINE_PATH = Path("quarantine/legacy-quantum-demonstrator/server.py")
SOVEREIGN_RUNTIME_ROOT = Path("sovereign-omega-v2/src")

QUARANTINE_MARKERS = (
    "LEGACY DIAGNOSTIC PROTOTYPE ONLY - ZERO RUNTIME OR VERIFICATION AUTHORITY",
    "CONTAINS MOCK/RNG FALLBACKS - PROHIBITED FROM AEGIS KERNEL & ADMISSION PIPELINES",
)

RUNTIME_SUFFIXES = {
    ".cjs",
    ".js",
    ".jsx",
    ".mjs",
    ".py",
    ".pyi",
    ".rs",
    ".ts",
    ".tsx",
}

_TARGET_TOKEN = re.compile(r"clients(?:[/\\]gemma-holon|\.gemma_holon)")
_IMPORT_TOKEN = re.compile(r"\b(?:import|export|from|require)\b")


class Violation(NamedTuple):
    code: str
    path: str
    line: int
    message: str


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_comment_only(line: str) -> bool:
    stripped = line.lstrip()
    return (
        stripped.startswith("#")
        or stripped.startswith("//")
        or stripped.startswith("/*")
        or stripped.startswith("*")
    )


def _contains_forbidden_import(line: str) -> bool:
    if _is_comment_only(line):
        return False
    return bool(_TARGET_TOKEN.search(line) and _IMPORT_TOKEN.search(line))


def _scan_runtime_imports(repo_root: Path) -> list[Violation]:
    src_root = repo_root / SOVEREIGN_RUNTIME_ROOT
    if not src_root.exists():
        return []

    violations: list[Violation] = []
    for path in sorted(p for p in src_root.rglob("*") if p.is_file()):
        if path.suffix.lower() not in RUNTIME_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            violations.append(
                Violation(
                    "RUNTIME_SOURCE_UNREADABLE",
                    _relative(path, repo_root),
                    0,
                    f"cannot inspect runtime source fail-closed: {exc}",
                )
            )
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            if _contains_forbidden_import(line):
                violations.append(
                    Violation(
                        "FORBIDDEN_LEGACY_IMPORT",
                        _relative(path, repo_root),
                        line_number,
                        "sovereign-omega-v2/src must not import clients/gemma-holon",
                    )
                )

    return violations


def collect_violations(repo_root: Path) -> list[Violation]:
    root = repo_root.resolve()
    violations: list[Violation] = []

    live_legacy = root / LEGACY_RUNTIME_PATH
    if live_legacy.exists():
        violations.append(
            Violation(
                "LEGACY_RUNTIME_PATH_PRESENT",
                LEGACY_RUNTIME_PATH.as_posix(),
                0,
                "legacy mock/RNG quantum demonstrator must live only in quarantine",
            )
        )

    quarantine = root / QUARANTINE_PATH
    if not quarantine.exists():
        violations.append(
            Violation(
                "QUARANTINE_ARTIFACT_MISSING",
                QUARANTINE_PATH.as_posix(),
                0,
                "quarantined historical demonstrator is missing",
            )
        )
    else:
        try:
            quarantine_text = quarantine.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            violations.append(
                Violation(
                    "QUARANTINE_UNREADABLE",
                    QUARANTINE_PATH.as_posix(),
                    0,
                    f"cannot inspect quarantine artifact fail-closed: {exc}",
                )
            )
        else:
            missing = [marker for marker in QUARANTINE_MARKERS if marker not in quarantine_text]
            if missing:
                violations.append(
                    Violation(
                        "QUARANTINE_HEADER_MISSING",
                        QUARANTINE_PATH.as_posix(),
                        0,
                        "required zero-authority quarantine marker(s) missing",
                    )
                )

    violations.extend(_scan_runtime_imports(root))
    return sorted(violations, key=lambda v: (v.path, v.line, v.code))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enforce AEGIS legacy quantum quarantine")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    violations = collect_violations(args.repo_root)
    if not violations:
        print("agent_governance_lint: PASS")
        return 0

    for violation in violations:
        location = f"{violation.path}:{violation.line}" if violation.line else violation.path
        print(f"{violation.code}: {location}: {violation.message}")
    print(f"agent_governance_lint: FAIL ({len(violations)} violation(s))")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
