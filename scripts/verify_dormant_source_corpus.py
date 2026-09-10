#!/usr/bin/env python3
"""Fail-closed verifier for quarantined source-skill corpora.

This verifier never imports or executes corpus code. It validates only bytes,
metadata and the authority boundary recorded in provenance.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "AEGIS_DORMANT_SOURCE_CORPUS_V1"
REQUIRED_STATUS = {
    "epistemic_status": "UNVERIFIED_SOURCE_CORPUS",
    "activation_status": "DORMANT_NOT_DISCOVERABLE_BY_ACTIVE_SKILL_PATH",
    "execution_status": "SOURCE_BYTES_NOT_EXECUTED",
    "authority_effect": "NONE",
}
FRONT_FIELD = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$")


class CorpusVerificationError(ValueError):
    pass


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise CorpusVerificationError("SKILL.md is missing YAML frontmatter")
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = FRONT_FIELD.match(line)
        if match:
            out[match.group(1)] = match.group(2).strip().strip("\"'")
    else:
        raise CorpusVerificationError("SKILL.md frontmatter is not closed")

    if not out.get("publisher"):
        for index, line in enumerate(lines[:80]):
            if line.strip() != "metadata:":
                continue
            for nested in lines[index + 1:index + 12]:
                if nested and not nested.startswith((" ", "\t")):
                    break
                match = re.match(r"^\s+publisher:\s*(.*?)\s*$", nested)
                if match:
                    out["publisher"] = match.group(1).strip().strip("\"'")
                    break
            break
    return out


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusVerificationError(f"invalid JSON at {path}") from exc
    if not isinstance(value, dict):
        raise CorpusVerificationError(f"JSON object required at {path}")
    return value


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    expected_suffix = Path("knowledge/source-corpora")
    parts = root.parts
    marker = expected_suffix.parts
    if len(parts) < len(marker) + 1 or tuple(parts[-(len(marker) + 1):-1]) != marker:
        raise CorpusVerificationError(
            "dormant corpus must live directly under knowledge/source-corpora/<id>"
        )

    provenance_path = root / "provenance.json"
    skills_root = root / "skills"
    source_manifest_path = root / "evidence" / "source-manifest.json"
    if not skills_root.is_dir():
        raise CorpusVerificationError("skills directory missing")
    provenance = _load_json(provenance_path)

    if provenance.get("schema") != SCHEMA:
        raise CorpusVerificationError("unsupported provenance schema")
    for key, expected in REQUIRED_STATUS.items():
        if provenance.get(key) != expected:
            raise CorpusVerificationError(f"{key} must equal {expected}")

    expected_destination = root.relative_to(Path.cwd().resolve()).as_posix() + "/skills"
    if provenance.get("destination_prefix") != expected_destination:
        raise CorpusVerificationError("destination_prefix does not bind this corpus path")

    files = sorted(path for path in skills_root.rglob("*") if path.is_file() or path.is_symlink())
    if not files:
        raise CorpusVerificationError("empty corpus")

    records: list[dict[str, Any]] = []
    license_counts: Counter[str] = Counter()
    publisher_counts: Counter[str] = Counter()
    package_count = 0
    for path in files:
        if path.is_symlink():
            raise CorpusVerificationError(f"symlink forbidden: {path}")
        rel = path.relative_to(skills_root).as_posix()
        data = path.read_bytes()
        records.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
        )
        if rel.endswith("/SKILL.md"):
            package_count += 1
            try:
                meta = _frontmatter(data.decode("utf-8", errors="strict"))
            except UnicodeDecodeError as exc:
                raise CorpusVerificationError(f"SKILL.md must be UTF-8: {rel}") from exc
            license_id = meta.get("license")
            publisher = meta.get("publisher")
            if not license_id or not publisher:
                raise CorpusVerificationError(f"license and publisher required: {rel}")
            license_counts[license_id] += 1
            publisher_counts[publisher] += 1

    payload = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    root_hash = hashlib.sha256(payload).hexdigest()

    if provenance.get("file_count") != len(records):
        raise CorpusVerificationError("file_count mismatch")
    if provenance.get("package_count") != package_count:
        raise CorpusVerificationError("package_count mismatch")
    if provenance.get("corpus_root_sha256") != root_hash:
        raise CorpusVerificationError("corpus_root_sha256 mismatch")
    if provenance.get("licenses") != dict(sorted(license_counts.items())):
        raise CorpusVerificationError("license census mismatch")
    if provenance.get("publishers") != dict(sorted(publisher_counts.items())):
        raise CorpusVerificationError("publisher census mismatch")

    if not source_manifest_path.is_file() or source_manifest_path.is_symlink():
        raise CorpusVerificationError("regular source manifest required")
    source_manifest_bytes = source_manifest_path.read_bytes()
    source_manifest_sha256 = hashlib.sha256(source_manifest_bytes).hexdigest()
    if provenance.get("source_manifest_sha256") != source_manifest_sha256:
        raise CorpusVerificationError("source manifest digest mismatch")

    source_sha = provenance.get("source_sha")
    if not isinstance(source_sha, str) or re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        raise CorpusVerificationError("full lowercase source SHA required")
    if not isinstance(provenance.get("source_pr"), int) or provenance["source_pr"] <= 0:
        raise CorpusVerificationError("positive source_pr required")

    receipt = {
        "schema": "AEGIS_DORMANT_SOURCE_CORPUS_VERIFICATION_V1",
        "corpus_id": provenance.get("corpus_id"),
        "corpus_root_sha256": root_hash,
        "file_count": len(records),
        "package_count": package_count,
        "licenses": dict(sorted(license_counts.items())),
        "publishers": dict(sorted(publisher_counts.items())),
        "source_sha": source_sha,
        "source_pr": provenance["source_pr"],
        "verification": "PASS",
        "execution_status": "SOURCE_BYTES_NOT_EXECUTED",
        "authority_effect": "NONE",
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    try:
        receipt = verify(args.root)
    except CorpusVerificationError as exc:
        print(json.dumps({"verification": "DENY", "error": str(exc), "authority_effect": "NONE"}))
        return 1
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
