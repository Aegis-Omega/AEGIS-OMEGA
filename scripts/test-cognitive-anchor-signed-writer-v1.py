#!/usr/bin/env python3
"""Fail-closed regression contract for GitHub-signed cognitive-anchor mutation."""
from pathlib import Path
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "cognitive-manifest-refresh.yml"


class CognitiveAnchorSignedWriterV1Tests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_existing_admission_boundary_is_preserved(self) -> None:
        required = (
            "workflow_dispatch:",
            "github.ref == 'refs/heads/main'",
            "GITHUB_ACTIONS_APP_ID: '15368'",
            "aegis / automaton-2",
            "aegis / automaton-3",
            "Main branch enforcement",
            "git check-ref-format --branch",
            'if [[ "$TARGET_REF" == "main" ]]',
            "repair/cognitive-anchor-*",
            'git ls-remote --exit-code --heads origin "refs/heads/$TARGET_REF"',
            "ref: refs/heads/${{ inputs.target_ref }}",
            "steps.admission.outputs.allowed == 'true'",
            "implicit zero parent is forbidden",
            "state_hash mismatch",
        )
        for needle in required:
            self.assertIn(needle, self.source)

    def test_writer_uses_github_signed_commit_api(self) -> None:
        self.assertIn("createCommitOnBranch", self.source)
        self.assertIn("expectedHeadOid", self.source)
        self.assertIn("GH_TOKEN: ${{ github.token }}", self.source)
        self.assertIn("SOURCE_SHA", self.source)
        self.assertIn("SIGNED_MANIFEST_COMMIT", self.source)

    def test_legacy_unsigned_git_commit_and_push_are_absent(self) -> None:
        self.assertNotIn('git commit -m "chore(manifest): refresh cognitive-state anchors"', self.source)
        self.assertNotIn('git push origin "HEAD:refs/heads/$TARGET_REF"', self.source)
        self.assertNotIn("git config user.name", self.source)
        self.assertNotIn("git config user.email", self.source)

    def test_target_head_is_rechecked_before_mutation(self) -> None:
        self.assertIn("git rev-parse HEAD", self.source)
        self.assertIn("STALE_HEAD", self.source)
        self.assertIn("live=", self.source)
        self.assertIn("expectedHeadOid: sourceSha", self.source)


if __name__ == "__main__":
    main()
