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
import hashlib
import re
from pathlib import Path
from typing import NamedTuple, Sequence


LEGACY_RUNTIME_PATH = Path("clients/gemma-holon/quantum/server.py")
QUARANTINE_PATH = Path("quarantine/legacy-quantum-demonstrator/server.py")
SOVEREIGN_RUNTIME_ROOT = Path("sovereign-omega-v2/src")
ORIGINAL_LEGACY_GIT_BLOB_SHA = "fb3e98a02630b5ca399bcbb8c388743494292e14"

QUARANTINE_MARKERS = (
    "LEGACY DIAGNOSTIC PROTOTYPE ONLY - ZERO RUNTIME OR VERIFICATION AUTHORITY",
    "CONTAINS MOCK/RNG FALLBACKS - PROHIBITED FROM AEGIS KERNEL & ADMISSION PIPELINES",
)
_QUARANTINE_HEADER_LINES = (
    "#!/usr/bin/env python3\n",
    f"# {QUARANTINE_MARKERS[0]}\n",
    f"# {QUARANTINE_MARKERS[1]}\n",
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
_GIT_BLOB_SHA = re.compile(r"^[0-9a-f]{40}$")


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


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _restore_historical_bytes(quarantine_text: str) -> bytes | None:
    """Remove only the two mandated quarantine marker lines.

    The shebang is part of the historical blob. Requiring the exact first three
    lines prevents a quarantine artifact from moving markers elsewhere and
    still passing the provenance check.
    """
    lines = quarantine_text.splitlines(keepends=True)
    if len(lines) < len(_QUARANTINE_HEADER_LINES):
        return None
    if tuple(lines[:3]) != _QUARANTINE_HEADER_LINES:
        return None
    restored = lines[0] + "".join(lines[3:])
    return restored.encode("utf-8")


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


def collect_violations(
    repo_root: Path,
    *,
    expected_legacy_blob_sha: str | None = None,
) -> list[Violation]:
    root = repo_root.resolve()
    violations: list[Violation] = []

    if expected_legacy_blob_sha is not None and _GIT_BLOB_SHA.fullmatch(expected_legacy_blob_sha) is None:
        raise ValueError("expected_legacy_blob_sha must be canonical lowercase Git SHA-1")

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

            if expected_legacy_blob_sha is not None:
                historical_bytes = _restore_historical_bytes(quarantine_text)
                if historical_bytes is None:
                    violations.append(
                        Violation(
                            "QUARANTINE_CONTENT_DRIFT",
                            QUARANTINE_PATH.as_posix(),
                            0,
                            "quarantine header layout cannot reconstruct the historical Git blob",
                        )
                    )
                else:
                    actual_blob_sha = _git_blob_sha(historical_bytes)
                    if actual_blob_sha != expected_legacy_blob_sha:
                        violations.append(
                            Violation(
                                "QUARANTINE_CONTENT_DRIFT",
                                QUARANTINE_PATH.as_posix(),
                                0,
                                "quarantine body differs from original Git blob "
                                f"{expected_legacy_blob_sha}; reconstructed={actual_blob_sha}",
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
    violations = collect_violations(
        args.repo_root,
        expected_legacy_blob_sha=ORIGINAL_LEGACY_GIT_BLOB_SHA,
    )
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
