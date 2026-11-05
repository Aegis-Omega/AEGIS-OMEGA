#!/usr/bin/env python3
"""Bind a CI-local Docker image observation to a successful exact-head GitHub run.

This is a signed-observation input, not an image signature or admission token.
No GitHub API access, secrets, image build or network calls occur in this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from harness.sdk.repository_knowledge import verify_remote_git_source

REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
REPOSITORY_ID = 1095915905
WORKFLOW = ".github/workflows/repository-knowledge.yml"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def verify_ci_image_observation(
    package: Mapping[str, Any],
    run: Mapping[str, Any],
    artifact: Mapping[str, Any],
    *,
    expected_head: str,
    expected_tree: str,
    dependencies: str,
) -> dict[str, Any]:
    """Return scoped HOLD-compatible observation or DENIED with exact reasons."""
    errors: set[str] = set()
    if not HEX40.fullmatch(expected_head) or not HEX40.fullmatch(expected_tree):
        errors.add("EXPECTED_SOURCE_INVALID")
    if (
        run.get("path") != WORKFLOW
        or run.get("head_sha") != expected_head
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("repository", {}).get("full_name") != REPOSITORY
        or run.get("head_repository", {}).get("full_name") != REPOSITORY
        or run.get("event") != "pull_request"
        or type(run.get("id")) is not int
        or run.get("id", 0) <= 0
    ):
        errors.add("SOURCE_WORKFLOW_UNTRUSTED")
    expected_artifact = f"runtime-export-{expected_head}"
    linked = artifact.get("workflow_run", {})
    if (
        artifact.get("name") != expected_artifact
        or artifact.get("expired") is not False
        or not SHA256.fullmatch(str(artifact.get("digest", "")))
        or type(artifact.get("id")) is not int
        or artifact.get("id", 0) <= 0
        or type(artifact.get("size_in_bytes")) is not int
        or artifact.get("size_in_bytes", 0) <= 0
        or linked.get("id") != run.get("id")
        or linked.get("head_sha") != expected_head
        or linked.get("repository_id") != REPOSITORY_ID
        or linked.get("head_repository_id") != REPOSITORY_ID
    ):
        errors.add("ARTIFACT_IDENTITY_MISMATCH")

    try:
        manifest = package["manifest"]
        source = package["docker-source-receipt"]
        final = package["final-image-receipt"]
        readback = package["github-readback"]
        if not all(isinstance(v, dict) for v in (manifest, source, final, readback)):
            raise ValueError("INVALID_PAYLOAD")
        replay = verify_remote_git_source(
            manifest, source,
            expected_head=expected_head,
            expected_repository=REPOSITORY,
            remote_commit_sha=expected_head,
            remote_tree_sha=expected_tree,
            final_image_receipt=final,
        )
        if replay.get("status") != "REMOTE_GIT_MATCH_ONLY" or replay.get("final_image_binding") != "CI_LOCAL_CONTENT_MATCH_ONLY":
            errors.add("IMAGE_SOURCE_BINDING_INVALID")
        if any(readback.get(field) != replay.get(field) for field in (
            "schema", "status", "source_head_sha", "source_tree_sha",
            "manifest_digest", "final_image_binding", "authority", "attestation",
        )):
            errors.add("GITHUB_READBACK_INCONSISTENT")
        image_id = final.get("image_id")
        if not SHA256.fullmatch(str(image_id)):
            errors.add("IMAGE_ID_INVALID")
    except (KeyError, TypeError, ValueError, AttributeError):
        errors.add("PACKAGE_INVALID")
        image_id = None
        replay = {}
    if not isinstance(dependencies, str) or not dependencies.strip():
        errors.add("DEPENDENCY_INVENTORY_MISSING")
    output = {
        "schema": "aegis-ci-local-image-observation/1",
        "status": "DENIED" if errors else "SOURCE_BOUND_CI_OBSERVATION",
        "reason_codes": sorted(errors),
        "repository": REPOSITORY,
        "source_head_sha": expected_head,
        "source_tree_sha": expected_tree,
        "source_workflow_run_id": run.get("id"),
        "source_artifact_id": artifact.get("id"),
        "source_artifact_reported_digest": artifact.get("digest"),
        "manifest_digest": replay.get("manifest_digest"),
        "ci_local_image_id": image_id,
        "dependencies_sha256": hashlib.sha256(dependencies.encode("utf-8")).hexdigest() if isinstance(dependencies, str) else None,
        "scope": "CI_LOCAL_IMAGE_OBSERVATION_ONLY",
        "image_signature": "NOT_PRESENT",
        "deployment_attested": False,
        "authority": "NOT_GRANTED",
        "agent_execution": "NOT_EXECUTED",
    }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--run-json", type=Path, required=True)
    parser.add_argument("--artifact-json", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = args.package_dir
    try:
        package = {
            name: json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
            for name in ("manifest", "docker-source-receipt", "final-image-receipt", "github-readback")
        }
        report = verify_ci_image_observation(
            package,
            json.loads(args.run_json.read_text(encoding="utf-8")),
            json.loads(args.artifact_json.read_text(encoding="utf-8")),
            expected_head=args.expected_head,
            expected_tree=args.expected_tree,
            dependencies=(directory / "final-image-python-dependencies.txt").read_text(encoding="utf-8"),
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"DENIED: CI image evidence unavailable ({type(error).__name__})")
        return 1
    if report["status"] != "SOURCE_BOUND_CI_OBSERVATION":
        print(json.dumps(report, sort_keys=True))
        return 1
    args.output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
