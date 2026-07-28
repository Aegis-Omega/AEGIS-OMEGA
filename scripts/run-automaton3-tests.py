#!/usr/bin/env python3
"""Run Automaton-3 tests and emit a deterministic summary."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = (
    ROOT / "sovereign-omega-v2/python/tests/test_automaton3.py",
    ROOT / "sovereign-omega-v2/python/tests/test_operator_visibility.py",
)

ASSERTION_TESTS = {
    "adaptive_attempts": {
        "test_adaptive_denial_attempts_k_1_10_100",
    },
    "state_preservation": {
        "test_01_unknown_coordinator_capability",
        "test_09_mismatched_parent_state",
        "test_12_stale_writer_lease",
        "test_13_replayed_fencing_token",
        "test_29_receipt_chain_break",
        "test_authority_admission_is_not_terminal_success",
    },
    "external_side_effect_absence": {
        "test_01_unknown_coordinator_capability",
        "test_14_duplicate_external_action",
        "test_15_replay_after_side_effect",
    },
    "operator_visibility": {
        "test_operator_visibility_cannot_be_suppressed",
        "test_authorization_mutation_and_cancellation_are_chained",
        "test_broken_operator_chain_is_denied",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    outputs: list[str] = []
    return_code = 0
    for test_file in TEST_FILES:
        result = subprocess.run(
            [sys.executable, str(test_file), "-v"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        outputs.append(result.stdout + result.stderr)
        if result.returncode != 0:
            return_code = result.returncode

    raw_log = "".join(outputs)
    observed_test_count = sum(int(value) for value in re.findall(r"Ran ([0-9]+) tests?", raw_log))
    expected_test_count = 54
    if observed_test_count != expected_test_count:
        return_code = return_code or 1
    log = raw_log.replace(str(ROOT), "<REPO>")
    log = re.sub(r"Ran ([0-9]+) tests? in [0-9.]+s", r"Ran \1 tests in <DURATION>s", log)
    passed_test_ids = sorted(set(re.findall(
        r"^(test_[A-Za-z0-9_]+).* \.\.\. ok$",
        log,
        flags=re.MULTILINE,
    )))
    passed = set(passed_test_ids)
    assertion_sets = {
        name: {
            "required_test_ids": sorted(required),
            "satisfied": required.issubset(passed),
        }
        for name, required in sorted(ASSERTION_TESTS.items())
    }
    all_assertions_satisfied = all(
        assertion["satisfied"] for assertion in assertion_sets.values()
    )
    if not all_assertions_satisfied:
        return_code = return_code or 1
    Path(args.log).write_text(log, encoding="utf-8")
    summary = {
        "schema_version": "1.0.0",
        "suite": "AEGIS_AUTOMATON3_AUTHORITY_ABUSE_V1",
        "expected_test_count": expected_test_count,
        "observed_test_count": observed_test_count,
        "adaptive_attempts": [1, 10, 100] if assertion_sets["adaptive_attempts"]["satisfied"] else [],
        "bypasses": 0 if return_code == 0 and all_assertions_satisfied else None,
        "state_preservation_asserted": assertion_sets["state_preservation"]["satisfied"],
        "external_side_effect_absence_asserted": assertion_sets["external_side_effect_absence"]["satisfied"],
        "operator_visibility_asserted": assertion_sets["operator_visibility"]["satisfied"],
        "assertion_sets": assertion_sets,
        "passed_test_ids": passed_test_ids,
        "return_code": return_code,
        "normalized_log_sha256": hashlib.sha256(log.encode()).hexdigest(),
    }
    body = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
    summary["summary_root"] = hashlib.sha256(body).hexdigest()
    Path(args.output).write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(log)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
