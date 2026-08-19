#!/usr/bin/env python3
"""Run integrated Automaton-3 tests and emit a deterministic summary."""
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
    ROOT / "sovereign-omega-v2/python/tests/test_authoritative_receipts.py",
    ROOT / "sovereign-omega-v2/python/tests/test_transition_receipts_pr1.py",
    ROOT / "sovereign-omega-v2/python/tests/test_transition_receipts_cli_pr1.py",
    ROOT / "sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py",
)
EXPECTED_TEST_COUNT = 115

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
        "test_08_stale_state_fence_and_lease_link_are_signed_denials_with_no_change",
        "test_24_every_receipt_kind_survives_persisted_restart_readback",
        "test_26_backdated_timestamp_cannot_revive_expired_lease",
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
    "cross_runtime_provenance": {
        "test_04_python_golden_vector_matches_schemas_and_derivations",
        "test_23_python_independently_verifies_and_replays_typescript_golden_vector",
    },
    "restart_readback": {
        "test_14_readback_failure_rolls_back_without_orphan_promotion",
        "test_24_every_receipt_kind_survives_persisted_restart_readback",
        "test_27_registry_readback_failure_rolls_back_without_partial_persistence",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    outputs: list[str] = []
    return_code = 0
    observed_counts: list[int] = []
    for test_file in TEST_FILES:
        result = subprocess.run(
            [sys.executable, str(test_file), "-v"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        output = result.stdout + result.stderr
        outputs.append(output)
        matches = re.findall(r"Ran ([0-9]+) tests?", output)
        if len(matches) == 1:
            observed_counts.append(int(matches[0]))
        else:
            return_code = return_code or 4
        if result.returncode != 0:
            return_code = result.returncode

    raw_log = "".join(outputs)
    observed_test_count = sum(observed_counts)
    test_count_complete = len(observed_counts) == len(TEST_FILES)
    test_count_matches_expected = test_count_complete and observed_test_count == EXPECTED_TEST_COUNT
    if not test_count_matches_expected:
        return_code = return_code or 4

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
    all_assertions_satisfied = all(item["satisfied"] for item in assertion_sets.values())
    if not all_assertions_satisfied:
        return_code = return_code or 1

    passed_all = return_code == 0 and test_count_matches_expected and all_assertions_satisfied
    Path(args.log).write_text(log, encoding="utf-8")
    summary = {
        "schema_version": "1.0.0",
        "suite": "AEGIS_AUTOMATON3_INTEGRATED_AUTHORITY_AND_EFFECT_V1",
        "expected_test_count": EXPECTED_TEST_COUNT,
        "observed_test_count": observed_test_count,
        "actual_test_count": observed_test_count,
        "test_count_complete": test_count_complete,
        "test_count_matches_expected": test_count_matches_expected,
        "adaptive_attempts": [1, 10, 100] if assertion_sets["adaptive_attempts"]["satisfied"] else [],
        "bypasses": 0 if passed_all else None,
        "state_preservation_asserted": assertion_sets["state_preservation"]["satisfied"],
        "external_side_effect_absence_asserted": assertion_sets["external_side_effect_absence"]["satisfied"],
        "operator_visibility_asserted": assertion_sets["operator_visibility"]["satisfied"],
        "cross_runtime_provenance_asserted": assertion_sets["cross_runtime_provenance"]["satisfied"],
        "restart_readback_asserted": assertion_sets["restart_readback"]["satisfied"],
        "transition_binding_asserted": passed_all,
        "receipt_separation_asserted": passed_all,
        "effect_receipt_schema_defined": True,
        "generic_effect_receipt_production_forbidden_asserted": passed_all,
        "legacy_receipt_effect_evidence_forbidden_asserted": passed_all,
        "pr2_effect_adapter_protocol_asserted": passed_all,
        "pr2_filesystem_effect_adapter_asserted": passed_all,
        "pr2_independent_pre_post_observation_asserted": passed_all,
        "pr2_adapter_bound_effect_evidence_production_asserted": passed_all,
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
