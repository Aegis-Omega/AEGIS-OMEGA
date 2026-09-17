#!/usr/bin/env python3
"""Check the approved writer bytes in an exact two-parent PR merge commit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

WORKFLOW = ".github/workflows/cognitive-manifest-refresh.yml"
# Reviewed gated dispatch writer at 0b656256813a23f07a280ca0e1f8358bb4eb9979.
APPROVED_SHA256 = "99f4c39ad780a77511347f7ac039557f428a0983f990f3304953dd2f636dd356"


def evaluate(repo, base_sha, head_sha, merge_sha):
    receipt = {
        "kind": "COGNITIVE_WRITER_MERGE_CHECK_V1",
        "outcome": "DENIED", "reason": "INVALID_COMMIT_ID",
        "base_sha": base_sha, "head_sha": head_sha, "merge_sha": merge_sha,
        "workflow_path": WORKFLOW, "approved_writer_sha256": APPROVED_SHA256,
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "EXACT_PR_MERGE_WRITER_BYTES_ONLY",
    }
    if any(not re.fullmatch(r"[0-9a-f]{40}", value) for value in (base_sha, head_sha, merge_sha)):
        return receipt

    def git(*args):
        # Never execute files from the candidate or honor replacement objects.
        return subprocess.check_output(
            ["git", "--no-replace-objects", "-C", str(repo), *args],
            stderr=subprocess.PIPE, timeout=30,
        )

    try:
        for sha in (base_sha, head_sha, merge_sha):
            if git("cat-file", "-t", sha).strip() != b"commit":
                receipt["reason"] = "GIT_OBJECT_UNAVAILABLE"
                return receipt
        parents, tree = git("show", "-s", "--format=%P%n%T", merge_sha).decode("ascii").splitlines()
        receipt.update(parents=parents.split(), tree_sha=tree)
        if receipt["parents"] != [base_sha, head_sha]:
            receipt["reason"] = "MERGE_PARENT_MISMATCH"
            return receipt
        entry = git("ls-tree", "-z", merge_sha, "--", WORKFLOW)
        receipt["reason"] = "WRITER_NOT_REGULAR_FILE"
        if not entry:
            return receipt
        metadata, path = entry.rstrip(b"\0").split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        if mode != "100644" or kind != "blob" or path.decode("utf-8") != WORKFLOW:
            return receipt
        receipt["writer_blob"] = blob
        receipt["reason"] = "WRITER_POLICY_MISMATCH"
        if int(git("cat-file", "-s", blob)) > 16384:
            return receipt
        source = git("cat-file", "blob", blob)
        receipt["writer_sha256"] = hashlib.sha256(source).hexdigest()
        if receipt["writer_sha256"] != APPROVED_SHA256:
            return receipt
        receipt.update(outcome="PASS", reason="APPROVED_WRITER_PRESERVED")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError):
        receipt["reason"] = "GIT_OBJECT_UNAVAILABLE"
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--merge-sha", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = evaluate(args.repo, args.base_sha, args.head_sha, args.merge_sha)
    rendered = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
