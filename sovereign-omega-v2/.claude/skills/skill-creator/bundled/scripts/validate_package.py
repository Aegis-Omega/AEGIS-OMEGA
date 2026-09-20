#!/usr/bin/env python3
"""Validate an AEGIS skill package for the skill-creator lifecycle.

This gate is deterministic and network-free. It validates changed SKILL.md
frontmatter, requires evals for newly added skills, validates eval structure,
and rejects duplicate skill names across the repository.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

SKILL_NAME_RE = re.compile(r"^name\\s*:\\s*(.+?)\\s*$")
SKILL_DESC_RE = re.compile(r"^description\\s*:\\s*(.+?)\\s*$")
SKIP_DIRS = {".git", "node_modules", "target", "dist", "build", ".venv", "__pycache__"}


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout


def frontmatter(path: Path) -> tuple[str | None, str | None]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None
    name = None
    description = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = SKILL_NAME_RE.match(line)
        if match:
            name = match.group(1).strip().strip("\'\\\"")
        match = SKILL_DESC_RE.match(line)
        if match:
            description = match.group(1).strip().strip("\'\\\"")
    return name, description


def validate_evals(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: cannot read evals JSON: {exc}"]
    if not isinstance(payload, list) or not (2 <= len(payload) <= 5):
        errors.append(f"{path}: evals must be a JSON array with 2-5 cases")
        return errors
    for index, case in enumerate(payload, 1):
        if not isinstance(case, dict):
            errors.append(f"{path}: case {index} must be an object")
            continue
        prompt = case.get("prompt")
        assertions = case.get("assertions")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{path}: case {index} prompt must be non-empty")
        if (
            not isinstance(assertions, list)
            or not (2 <= len(assertions) <= 12)
            or not all(isinstance(a, str) and a.strip() for a in assertions)
        ):
            errors.append(f"{path}: case {index} assertions must contain 2-12 non-empty strings")
    return errors


def all_skill_names(root: Path) -> tuple[dict[str, list[str]], list[str]]:
    by_name: dict[str, list[str]] = {}
    errors: list[str] = []
    for path in sorted(root.rglob("SKILL.md"), key=lambda p: p.as_posix()):
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        try:
            name, description = frontmatter(path)
        except Exception as exc:
            errors.append(f"{relative}: cannot read skill: {exc}")
            continue
        if not name:
            errors.append(f"{relative}: missing frontmatter name")
            continue
        if not description:
            errors.append(f"{relative}: missing frontmatter description")
        by_name.setdefault(name, []).append(relative.as_posix())
    return by_name, errors


def changed_skills(root: Path, base: str, head: str) -> list[dict[str, str]]:
    output = git(root, "diff", "--name-status", f"{base}...{head}", "--", ":(glob)**/SKILL.md")
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\\t")
        status = parts[0]
        path = parts[-1]
        rows.append({"status": status, "path": path})
    return rows


def evaluate(root: Path, base: str, head: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    changes = changed_skills(root, base, head)
    validated_evals: list[str] = []

    for change in changes:
        status = change["status"]
        relative = change["path"]
        path = root / relative
        if status.startswith("D"):
            continue
        if not path.is_file():
            errors.append(f"{relative}: changed skill is not a regular file")
            continue
        name, description = frontmatter(path)
        if not name:
            errors.append(f"{relative}: missing frontmatter name")
        if not description:
            errors.append(f"{relative}: missing frontmatter description")
        elif len(description.strip()) < 40:
            warnings.append(f"{relative}: description is unusually short for reliable triggering")

        eval_path = path.parent / "evals" / "evals.json"
        if status.startswith("A"):
            if not eval_path.is_file():
                errors.append(f"{relative}: new skill requires evals/evals.json")
            else:
                errors.extend(validate_evals(eval_path))
                validated_evals.append(eval_path.relative_to(root).as_posix())
        elif eval_path.is_file():
            errors.extend(validate_evals(eval_path))
            validated_evals.append(eval_path.relative_to(root).as_posix())

    by_name, catalog_errors = all_skill_names(root)
    errors.extend(catalog_errors)
    duplicates = {name: paths for name, paths in by_name.items() if len(paths) > 1}
    for name, paths in sorted(duplicates.items()):
        errors.append(f"duplicate skill name {name!r}: {', '.join(paths)}")

    receipt: dict[str, Any] = {
        "schema": "aegis.skill-package-validation.v1",
        "base_sha": base,
        "head_sha": head,
        "changed_skills": changes,
        "catalog_skill_count": sum(len(paths) for paths in by_name.values()),
        "validated_evals": sorted(validated_evals),
        "warnings": warnings,
        "errors": errors,
        "outcome": "PASS" if not errors else "FAIL",
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    receipt = evaluate(root, args.base_sha, args.head_sha)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
