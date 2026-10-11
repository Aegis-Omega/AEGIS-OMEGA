"""Fail-closed exact-head M2 regression runner; no runtime bootstrap required.

Usage: EXPECTED_HEAD_SHA="$(git rev-parse HEAD)" python tests/run_m2_exact_head_replay.py
Prints one machine-readable JSON receipt to stdout and human test output to stderr.
Never modifies the repository or starts an AEGIS subsystem.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import traceback
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PYTHON = ROOT / "sovereign-omega-v2" / "python"
SOURCES = (
    "sovereign-omega-v2/python/core_matrix.py",
    "sovereign-omega-v2/python/bridge.py",
    # Source-bound ingress/governance tests compile the *frozen* gate.py class.
    # Omitting this dependency from receipts makes exact-head evidence incomplete.
    "sovereign-omega-v2/python/gate.py",
    "sovereign-omega-v2/python/tests/fixtures/m2_sequence_domain_contract.json",
    "sovereign-omega-v2/python/tests/fixtures/M2_Ring_Design_Review_2026-10-11.md",
    "sovereign-omega-v2/python/tests/test_m2_layout_diagnostic.py",
    "sovereign-omega-v2/python/tests/test_m2_runtime_replay.py",
    "sovereign-omega-v2/python/tests/test_m2_mutation_guard.py",
    "sovereign-omega-v2/python/tests/run_m2_exact_head_replay.py",
    ".github/workflows/m2-layout-diagnostic.yml",
)


# Explicitly reviewed test inventory. A renamed/deleted test cannot
# silently turn an incomplete suite into a green receipt.
REQUIRED_TEST_NAMES = {
    "test_m2_layout_diagnostic.py": [
        "test_actual_http_gate_handler_rejects_remote_and_unbounded_input",
        "test_both_live_m2_writer_sequence_sources_are_enumerated",
        "test_bridge_ack_sequence_advances_after_both_signal_writes",
        "test_bridge_discards_event_router_seq_but_forwards_gate_signal_seq",
        "test_bridge_m2_failure_does_not_apply_governance_or_ack",
        "test_bridge_rejects_invalid_gate_sequence_before_any_gate_mutation",
        "test_current_source_formula_is_bound_to_diagnostic_contract",
        "test_event_sequence_overflow_guard_precedes_m1_mutation",
        "test_gate_cors_preflight_rejected_without_changing_other_routes",
        "test_gate_ingress_and_effect_branches_are_distinct",
        "test_legacy_offset_domain_is_floor_region_len_over_eight",
        "test_legacy_phase_wrap_witness_overlaps_eight_byte_windows",
        "test_legacy_unaligned_offset_witness_is_nine_for_real_profiles",
        "test_m2_record_constructed_before_single_buffer_write",
        "test_real_gate_source_rejects_unhashable_proposal_before_mutation",
        "test_unadmitted_policy_cannot_be_promoted_by_contract_toggle"
    ],
    "test_m2_runtime_replay.py": [
        "test_actual_M2_writes_aligned_eight_byte_records",
        "test_circular_wrap_is_confined_to_source_namespace",
        "test_default_and_cloud_profiles_without_large_allocation",
        "test_gate_signal_does_not_overwrite_event_record",
        "test_independent_sources_cannot_alias_on_same_numeric_sequence",
        "test_policy_source_bound_and_not_admitted",
        "test_q16_16_telemetry_unchanged_by_address_policy",
        "test_reject_invalid_address_inputs_before_mutating_state",
        "test_small_region_exhaustive_write_footprint",
        "test_two_writer_concurrent_interleavings_are_disjoint"
    ],
    "test_m2_mutation_guard.py": [
        "test_bool_sequence_mutant_accepts_invalid_input",
        "test_legacy_byte_modulus_mutant_exhibits_unaligned_write",
        "test_namespace_merge_mutant_exhibits_cross_source_alias",
        "test_unaligned_address_mutant_exhibits_bad_alignment"
    ]
}


def _test_method_names(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _test_method_names(item)
        else:
            yield item.id().rsplit('.', 1)[-1]


def _git(*args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return process.stdout.strip()


def main() -> int:
    expected = os.environ.get("EXPECTED_HEAD_SHA", "").strip()
    receipt = {
        "schema": "aegis.m2.exact-head-replay.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "expected_head_sha": expected or None,
        "actual_head_sha": None,
        "tracked_files_clean": None,
        "files_sha256": {},
        "tests_run": 0,
        "expected_tests": sum(len(names) for names in REQUIRED_TEST_NAMES.values()),
        "test_inventory": {},
        "failures": 0,
        "errors": 0,
        "disposition": "BLOCKED_UNBOUND_HEAD",
        "authority_effect": "NONE",
    }
    try:
        actual = _git("rev-parse", "HEAD")
        receipt["actual_head_sha"] = actual
        if not expected or len(expected) != 40 or expected != actual:
            receipt["disposition"] = "BLOCKED_HEAD_MISMATCH"
            return 2
        dirty = _git("status", "--porcelain", "--untracked-files=no", "--", *SOURCES)
        receipt["tracked_files_clean"] = not bool(dirty)
        if dirty:
            receipt["disposition"] = "BLOCKED_DIRTY_SOURCES"
            return 2
        for path in SOURCES:
            receipt["files_sha256"][path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

        # Load by exact checkout path; do not depend on a global "tests" package.
        suite = unittest.TestSuite()
        for index, name in enumerate(("test_m2_layout_diagnostic.py",
                                      "test_m2_runtime_replay.py",
                                      "test_m2_mutation_guard.py")):
            path = PYTHON / "tests" / name
            spec = importlib.util.spec_from_file_location(
                "aegis_m2_exact_head_test_" + str(index), str(path))
            if spec is None or spec.loader is None:
                raise ImportError("Cannot load exact-head test file " + name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            loaded = unittest.defaultTestLoader.loadTestsFromModule(module)
            actual_names = sorted(_test_method_names(loaded))
            expected_names = sorted(REQUIRED_TEST_NAMES[name])
            receipt["test_inventory"][name] = {
                "expected": len(expected_names), "loaded": len(actual_names),
                "names": actual_names,
            }
            if actual_names != expected_names:
                raise RuntimeError(
                    "TEST_INVENTORY_DRIFT " + name + ": expected "
                    + repr(expected_names) + ", got " + repr(actual_names)
                )
            suite.addTests(loaded)
        sink = io.StringIO()
        result = unittest.TextTestRunner(stream=sink, verbosity=2).run(suite)
        print(sink.getvalue(), file=sys.stderr)
        receipt["tests_run"] = result.testsRun
        receipt["failures"] = len(result.failures)
        receipt["errors"] = len(result.errors)
        receipt["disposition"] = (
            "PASS" if result.wasSuccessful()
            and result.testsRun == receipt["expected_tests"]
            else "FAIL_TESTS"
        )
        return 0 if receipt["disposition"] == "PASS" else 1
    except Exception as exc:  # preserve machine-readable BLOCKED receipt on loader errors
        receipt["disposition"] = "BLOCKED_REPLAY_ERROR"
        receipt["error_type"] = type(exc).__name__
        # Show the first real failing source or module import, not merely the
        # exception class. Bound printed evidence to avoid giant receipts.
        receipt["error_message"] = str(exc)[:2048]
        receipt["error_traceback"] = traceback.format_exc(limit=12)[-8192:]
        print(receipt["error_traceback"], file=sys.stderr)
        return 2
    finally:
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    raise SystemExit(main())
