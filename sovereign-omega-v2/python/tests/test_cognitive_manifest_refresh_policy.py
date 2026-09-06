#!/usr/bin/env python3
"""Static falsifiers for the cognitive-manifest exact-head policy."""
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github/workflows/cognitive-manifest-refresh.yml"


class CognitiveManifestRefreshPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_refresh_is_read_only_and_never_creates_an_unchecked_child_head(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("git commit", self.workflow)
        self.assertNotIn("git push", self.workflow)

    def test_parent_is_bound_to_the_actual_pull_request_base(self) -> None:
        self.assertIn(
            "BASE_SHA: ${{ github.event.pull_request.base.sha || inputs.parent_sha }}",
            self.workflow,
        )
        self.assertIn('git show "$BASE_SHA:.claude.json"', self.workflow)

    def test_missing_or_invalid_parent_fails_closed(self) -> None:
        self.assertNotIn("printf '0%.0s'", self.workflow)
        self.assertIn('test -s "$parent_manifest"', self.workflow)
        self.assertIn('[[ "$parent_hash" =~ ^[0-9a-f]{64}$ ]]', self.workflow)

    def test_expected_anchors_are_generated_outside_the_candidate_tree(self) -> None:
        self.assertIn('--output-dir "$RUNNER_TEMP/cognitive-anchors"', self.workflow)
        self.assertIn(
            'cmp -s "$RUNNER_TEMP/cognitive-anchors/.claude.json" .claude.json',
            self.workflow,
        )
        self.assertIn(
            'cmp -s "$RUNNER_TEMP/cognitive-anchors/skill-hashes.sha256" skill-hashes.sha256',
            self.workflow,
        )


if __name__ == "__main__":
    unittest.main()
