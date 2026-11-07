#!/usr/bin/env python3
"""Read-only, fail-closed check of literal Docker Compose build stage references.

Checks static service build blocks of the form build: {context,dockerfile,target}.
Not a complete YAML parser, Docker build or deployment proof. Dynamic/unsupported
build declarations are UNKNOWN, never silently accepted as valid targets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

_SERVICE = re.compile(r"^  ([A-Za-z_][\w-]*):[ \t]*(?:#.*)?$", re.M)
_BUILD = re.compile(r"^    build:[ \t]*(.*)$", re.M)
_SUBKEY = re.compile(r"^      (context|dockerfile|target):[ \t]*(.*)$", re.M)
_FROM = re.compile(r"^\s*FROM\s+\S+?(?:\s+AS\s+([A-Za-z][\w.-]*))?\s*(?:#.*)?$", re.I | re.M)


def _literal(raw: str) -> str | None:
    raw = raw.strip()
    if raw.startswith(("'", '"')) and raw.endswith(raw[:1]) and len(raw) >= 2:
        raw = raw[1:-1]
    elif " #" in raw:
        raw = raw.split(" #", 1)[0].rstrip()
    if not raw or any(x in raw for x in ("${", "{{", "!", "\n")):
        return None
    return raw


def evaluate(repo: Path, compose: str) -> dict:
    """Observe only the supported literal subset; never infer from runtime."""
    repo = repo.resolve()
    if not re.search(r"^services:\s*$", compose, re.M):
        return {"status": "UNKNOWN", "services": [], "reasons": ["SERVICES_MAPPING_NOT_FOUND"]}
    section = re.search(r"^services:\s*$(.*?)(?=^[A-Za-z][\w-]*:\s*$|\Z)", compose, re.M | re.S)
    if not section:
        return {"status": "UNKNOWN", "services": [], "reasons": ["SERVICES_SECTION_UNPARSEABLE"]}
    source = section.group(1)
    spans = list(_SERVICE.finditer(source))
    if not spans:
        return {"status": "UNKNOWN", "services": [], "reasons": ["NO_PARSEABLE_SERVICES"]}
    records = []
    for i, match in enumerate(spans):
        name = match.group(1)
        body = source[match.end():spans[i + 1].start() if i + 1 < len(spans) else len(source)]
        builds = list(_BUILD.finditer(body))
        if not builds:
            continue
        if len(builds) != 1:
            records.append({"service": name, "status": "UNKNOWN", "reason": "BUILD_BLOCK_AMBIGUOUS"})
            continue
        build = builds[0]
        if build.group(1).strip():
            records.append({"service": name, "status": "UNKNOWN", "reason": "NON_MAPPING_BUILD_UNSUPPORTED"})
            continue
        remainder = body[build.end():]
        nxt = re.search(r"^    [A-Za-z][\w-]*:\s*", remainder, re.M)
        block = remainder[:nxt.start()] if nxt else remainder
        items = {}
        ambiguous = False
        for key, value in _SUBKEY.findall(block):
            if key in items:
                ambiguous = True
            items[key] = _literal(value)
        if ambiguous or not items.get("context") or not items.get("dockerfile"):
            records.append({"service": name, "status": "UNKNOWN", "reason": "BUILD_BINDING_NOT_LITERAL"})
            continue
        if "target" in items and items["target"] is None:
            records.append({"service": name, "status": "UNKNOWN", "reason": "BUILD_TARGET_NOT_LITERAL"})
            continue
        dockerfile = (repo / items["context"] / items["dockerfile"]).resolve()
        if not dockerfile.is_relative_to(repo):
            records.append({"service": name, "status": "UNKNOWN", "reason": "DOCKERFILE_OUTSIDE_REPOSITORY"})
            continue
        relative = dockerfile.relative_to(repo).as_posix()
        if not dockerfile.is_file():
            records.append({"service": name, "dockerfile": relative, "status": "FAILED", "reason": "DOCKERFILE_MISSING"})
            continue
        docker_source = dockerfile.read_text(encoding="utf-8")
        from_lines = [l for l in docker_source.splitlines() if re.match(r"^\s*FROM\s+", l, re.I)]
        stages = [m.group(1) for m in _FROM.finditer(docker_source)]
        if not from_lines or len(from_lines) != len(stages):
            records.append({"service": name, "dockerfile": relative, "status": "UNKNOWN", "reason": "DOCKER_STAGES_UNPARSEABLE"})
            continue
        target = items.get("target")
        status = "PASS" if target is None or target.lower() in {s.lower() for s in stages if s} else "FAILED"
        records.append({"service": name, "dockerfile": relative, "target": target,
                        "stages": [s for s in stages if s], "status": status,
                        "reason": "TARGET_AVAILABLE" if target and status == "PASS" else
                                  "DEFAULT_STAGE" if not target else "BUILD_TARGET_NOT_FOUND"})
    if not records:
        return {"status": "UNKNOWN", "services": [], "reasons": ["NO_BUILD_MAPPING_FOUND"]}
    status = "FAILED" if any(r["status"] == "FAILED" for r in records) else (
        "UNKNOWN" if any(r["status"] == "UNKNOWN" for r in records) else "PASS")
    return {"status": status, "services": records, "scope": "literal-build-stage-validation-only"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--compose", default="docker-compose.yml")
    args = ap.parse_args()
    repo = args.repo.resolve()
    compose = (repo / args.compose).resolve()
    if not compose.is_relative_to(repo) or not compose.is_file():
        print(json.dumps({"status": "UNKNOWN", "reason": "COMPOSE_FILE_UNAVAILABLE"}))
        return 2
    result = evaluate(repo, compose.read_text(encoding="utf-8"))
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else (1 if result["status"] == "FAILED" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
