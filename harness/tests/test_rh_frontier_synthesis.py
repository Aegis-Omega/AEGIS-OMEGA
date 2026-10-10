"""AEGIS source-bound proof-frontier synthesis, not a simulated Lean proof."""
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from harness.sdk.research.rh_frontier import (
    SOURCE_DIR, analyze, canonical, git_blob, load_sources,
    render_lean, render_model_task, sha256,
)


class FormalResearchFrontierTests(unittest.TestCase):
    def test_real_cross_lane_stronger_cutoff(self):
        result = analyze()
        old = result["previous_lower_window_cutoff"]
        new = result["candidate_lower_window_cutoff"]
        delta = result["cutoff_improvement"]
        self.assertEqual(Fraction(**old), Fraction(693, 2000))
        self.assertEqual(Fraction(**new), Fraction(21, 40))
        self.assertEqual(Fraction(**delta), Fraction(357, 2000))
        self.assertGreater(Fraction(**new), Fraction(**old))
        self.assertEqual(result["old_comparison"], "<")
        self.assertEqual(result["new_comparison"], "≤")
        self.assertIn("rh_of_windows_from_21_40", result["new_provider"])
        self.assertFalse(result["unconditional_riemann_hypothesis_proven"])
        self.assertFalse(result["kernel_verified_on_source_head"])
        self.assertFalse(result["authority_granted"])
        self.assertEqual(result["operational_admission"], "NOT_ADMITTED")
        self.assertEqual(result["remaining_obligations"][-1]["status"], "OPEN")

    def test_pinned_actual_upstream_references(self):
        manifest, source = load_sources()
        self.assertEqual(manifest["head_sha"], "92b7943aea75236ebb25fc24106081153d765257")
        self.assertEqual(
            manifest["files"]["krein_l105"]["git_blob"],
            "71ec4bfe3e581235bc08025ce744f299469af361",
        )
        self.assertIn("theorem rh_of_windows_from_21_40", source["krein_l105"])
        self.assertIn("theorem riemannHypothesis", source["official"])
        self.assertEqual(analyze()["source_sha256"]["official"],
                         sha256(source["official"].encode("utf-8")))

    def test_output_is_reproducible_and_machine_actionable(self):
        first, second = analyze(), analyze()
        self.assertEqual(canonical(first), canonical(second))
        lean = render_lean(first)
        self.assertIn("import RHWindowL105FinalV1", lean)
        self.assertIn("hLarge : ∀ L : ℝ, (21 / 40 : ℝ) ≤ L", lean)
        self.assertIn("rh_of_windows_from_21_40 hLarge", lean)
        self.assertNotIn("sorry", lean)
        self.assertNotIn("admit", lean)
        model = render_model_task(first)
        self.assertEqual(model["goal"], first["remaining_obligations"][-1]["proposition"])
        self.assertEqual(model["model_response_state"], "UNVERIFIED_CANDIDATE_ONLY")
        self.assertEqual(model["report_sha256"], first["report_sha256"])

    def mutate(self, file: str, edit, rebind: bool = False) -> Path:
        self.addCleanup(lambda: None)
        directory = Path(tempfile.mkdtemp(prefix="aegis-proof-frontier-test-"))
        self.addCleanup(shutil.rmtree, directory)
        for path in SOURCE_DIR.iterdir():
            shutil.copy2(path, directory / path.name)
        target = directory / (file + ".lean")
        altered = edit(target.read_text(encoding="utf-8"))
        target.write_text(altered, encoding="utf-8")
        if rebind:
            manifest = json.loads((directory / "manifest.json").read_text())
            manifest["files"][file]["git_blob"] = git_blob(target.read_bytes())
            (directory / "manifest.json").write_text(json.dumps(manifest))
        return directory

    def test_tampered_source_without_rebinding_denied(self):
        directory = self.mutate(
            "krein_l105", lambda s: s.replace("21 / 40", "1 / 40", 1),
        )
        with self.assertRaisesRegex(ValueError, "SOURCE_TAMPER_OR_DRIFT"):
            analyze(directory)

    def test_weaker_competing_source_not_promoted(self):
        directory = self.mutate(
            "krein_l105", lambda s: s.replace("21 / 40 ≤ L", "1 / 40 ≤ L"),
            rebind=True,
        )
        with self.assertRaisesRegex(ValueError, "NO_STRONGER_PRODUCER"):
            analyze(directory)

    def test_target_changed_cannot_be_silently_rewritten(self):
        directory = self.mutate(
            "official",
            lambda s: s.replace(
                "apply AEGIS.RHSmallWindowCanonicalJoinV1.riemannHypothesis_of_above_693_over_2000_v1",
                "exact True.intro",
                1,
            ),
            rebind=True,
        )
        with self.assertRaisesRegex(ValueError, "OFFICIAL_TARGET_NO_LONGER_MATCHES_PINNED_BRANCH"):
            analyze(directory)

    def test_unexpected_window_premise_rejected(self):
        directory = self.mutate(
            "krein_l105",
            lambda s: s.replace(
                "21 / 40 ≤ L → WindowArithmeticNonpositiveV1 L",
                "21 / 40 ≤ L → True",
                1,
            ),
            rebind=True,
        )
        with self.assertRaisesRegex(ValueError, "UNIQUE_LARGE_WINDOW_PREMISE"):
            analyze(directory)

    def test_invalid_lean_research_output_request_denied(self):
        with self.assertRaises(ValueError):
            render_lean({"kind": "FAKE_PROOF", "new_provider": "fake"})

    def test_source_cannot_claim_kernel_pass_from_static_parsing(self):
        result = analyze()
        self.assertEqual(result["static_compatibility"], "SOURCE_HEADER_COMPATIBLE_ONLY")
        self.assertTrue(all(item["status"] == "UNVERIFIED"
                            for item in result["remaining_obligations"][:2]))
        self.assertFalse(result["unconditional_riemann_hypothesis_proven"])


if __name__ == "__main__":
    unittest.main()
