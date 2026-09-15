#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
evidence = root / "evidence"
pins = json.loads((root / "PINS.json").read_text())

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse_source_hashes(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        digest, filename = line.split(None, 1)
        out[Path(filename).name] = digest
    return out

integration_log = (evidence / "integration-test.log").read_text(errors="replace")
probe_log = (evidence / "o2-probe.log").read_text(errors="replace")
if "test result: ok. 8 passed; 0 failed;" not in integration_log:
    raise SystemExit("INTEGRATION_COUNT_NOT_VERIFIED")
if "test result: ok. 1 passed; 0 failed;" not in probe_log:
    raise SystemExit("PROBE_COUNT_NOT_VERIFIED")

receipt = {
    "schema": "AEGIS_PARETOMOD9_RUST_FRESH_REPLAY_RECEIPT_V1",
    "historical_source_head": pins["historical_source_head"],
    "historical_source_blobs": pins["source_blobs"],
    "historical_ci": {
        "run_id": pins["historical_workflow_run_id"],
        "job_id": pins["historical_cl_psi_job_id"],
        "toolchain_binding": pins["historical_toolchain_binding"],
        "toolchain_source": pins["historical_toolchain_source"],
        "fresh_run_claimed_same_toolchain": False,
    },
    "fresh_toolchain": pins["fresh_toolchain"],
    "github_helper_sha": os.environ.get("GITHUB_SHA"),
    "github_run_id": os.environ.get("GITHUB_RUN_ID"),
    "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    "integration": {
        "target": pins["integration_target"],
        "command": pins["integration_command"],
        "passed": 8,
        "failed": 0,
        "status": "PASS",
    },
    "o2_fail_closed_probe": {
        "command": pins["probe_command"],
        "passed": 1,
        "failed": 0,
        "status": "PASS",
        "expected_error": "ParetoModeAError::ProfileUndefined",
        "probe_sha256": sha256(root / "paretomod9_o2_profile_probe.rs"),
    },
    "source_sha256": parse_source_hashes(evidence / "source-sha256.txt"),
    "logs_sha256": {
        "rustc-version.log": sha256(evidence / "rustc-version.log"),
        "cargo-version.log": sha256(evidence / "cargo-version.log"),
        "integration-test.log": sha256(evidence / "integration-test.log"),
        "o2-probe.log": sha256(evidence / "o2-probe.log"),
        "source-sha256.txt": sha256(evidence / "source-sha256.txt"),
        "o2-probe-sha256.txt": sha256(evidence / "o2-probe-sha256.txt"),
    },
    "historical_tracked_source_modified": False,
    "full_cl_psi_suite_replayed": False,
    "scope": pins["scope"],
    "analytic_weil_proof": False,
    "riemann_hypothesis_proof": False,
    "repository_admission": "NOT_GRANTED",
    "merge": "NONE",
    "authority_effect": "NONE",
}
(evidence / "rust-replay-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
