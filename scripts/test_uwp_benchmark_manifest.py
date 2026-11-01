import copy
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import uwp_benchmark_manifest as benchmark

FIXTURE = Path(__file__).parent / "examples/uwp09_fixture_NOT_RUN.json"


class BenchmarkManifestTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_preserves_population_and_does_not_report_unrun_results(self):
        receipt = benchmark.validate_manifest(self.payload)
        self.assertEqual(receipt["population_denominator"], 1)
        self.assertEqual(receipt["executed_denominator"], 0)
        for field in (
            "success_rate", "false_passes", "crash_recovery", "budget",
            "latency", "manual_interventions", "confidence_intervals",
        ):
            self.assertIsNone(receipt[field])
        self.assertEqual(receipt["hidden_holdout"], "NOT_PROVIDED")
        self.assertEqual(receipt["world_best"], "UNESTABLISHED")
        self.assertEqual(receipt["paired_evaluator"], "NOT_AVAILABLE_IN_BASE")

    def test_duplicate_task_ids_are_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"].append(copy.deepcopy(payload["cases"][0]))
        with self.assertRaisesRegex(benchmark.InvalidManifest, "duplicate task id"):
            benchmark.validate_manifest(payload)

    def test_missing_comparator_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["arm_revisions"].pop("no_change")
        with self.assertRaisesRegex(benchmark.InvalidManifest, "all five comparison arms"):
            benchmark.validate_manifest(payload)

    def test_unknown_budget_must_be_explicit(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["budget"]["wall_ms"] = 1000
        with self.assertRaisesRegex(benchmark.InvalidManifest, "unknown budget"):
            benchmark.validate_manifest(payload)

    def test_abstention_truth_must_match_expected_action(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["abstention_correct"] = True
        with self.assertRaisesRegex(benchmark.InvalidManifest, "abstention truth"):
            benchmark.validate_manifest(payload)

    def test_all_thirteen_axes_are_required(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["quality_axes"].pop("sonic")
        with self.assertRaisesRegex(benchmark.InvalidManifest, "all 13 quality axes"):
            benchmark.validate_manifest(payload)

    def test_unmeasured_axis_cannot_claim_evidence(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["quality_axes"]["accessibility"]["evidence_sha256"] = "a" * 64
        with self.assertRaisesRegex(benchmark.InvalidManifest, "cannot carry measurement evidence"):
            benchmark.validate_manifest(payload)

    def test_measured_axis_requires_method_evidence_and_reviewer_reference(self):
        payload = copy.deepcopy(self.payload)
        axis = payload["cases"][0]["quality_axes"]["accessibility"]
        axis.update(status="MEASURED", measurement_method="mock", evidence_sha256="bad")
        with self.assertRaisesRegex(benchmark.InvalidManifest, "SHA-256 digest"):
            benchmark.validate_manifest(payload)

    def test_unknown_standard_metadata_is_accepted_as_unknown(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["standards"] = [{
            "id": "WCAG22",
            "issuer": "UNKNOWN",
            "publisher_url": "UNKNOWN",
            "document_id": "UNKNOWN",
            "edition_date": "UNKNOWN",
            "status_at_observation": "UNKNOWN",
            "domain_scope": "UNKNOWN",
            "applicability_decision": "UNKNOWN",
            "measurement_method": "UNKNOWN",
            "checked_at": "UNKNOWN",
        }]
        self.assertEqual(benchmark.validate_manifest(payload)["status"], "FIXTURE_ONLY_NOT_RUN")

    def test_not_applicable_axis_must_bind_to_task_definition(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["quality_axes"]["sonic"]["evidence_sha256"] = "a" * 64
        with self.assertRaisesRegex(benchmark.InvalidManifest, "must bind to task bytes"):
            benchmark.validate_manifest(payload)

    def test_fixture_manifest_cannot_be_marked_executed(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["run_state"] = "PASS"
        with self.assertRaisesRegex(benchmark.InvalidManifest, "does not accept execution claims"):
            benchmark.validate_manifest(payload)

    def test_json_duplicate_keys_are_rejected(self):
        with self.assertRaisesRegex(benchmark.InvalidManifest, "duplicate JSON key"):
            json.loads('{"schema":"a","schema":"b"}', object_pairs_hook=benchmark.unique_object)

    def test_changed_task_bytes_are_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["cases"][0]["task_sha256"] = "a" * 64
        with self.assertRaisesRegex(benchmark.InvalidManifest, "task text digest mismatch"):
            benchmark.validate_manifest(payload)

    def test_cli_reports_invalid_input_with_nonzero_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{"schema":"wrong"}', encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(benchmark.main(["--input", str(path)]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
