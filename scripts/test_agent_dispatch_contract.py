#!/usr/bin/env python3
"""Static wiring contract for the paid AEGIS agent-dispatch boundary."""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/agent-dispatch.yml"
BOUNDARY = ROOT / "vertex/authority_boundary.py"
DOCKERFILE = ROOT / "vertex/Dockerfile"
DEPLOY = ROOT / "vertex/cloudbuild.yaml"


class AgentDispatchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.boundary = BOUNDARY.read_text(encoding="utf-8")
        cls.dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        cls.deploy = DEPLOY.read_text(encoding="utf-8")

    def test_workflow_targets_real_constitutional_ci(self) -> None:
        self.assertIn('workflows: ["⊕ AEGIS-Ω Constitutional Automaton"]', self.workflow)
        self.assertNotIn('workflows: ["CI"]', self.workflow)

    def test_pr_metadata_uses_default_branch_workflow_not_untrusted_pr_workflow(self) -> None:
        self.assertIn("pull_request_target:", self.workflow)
        self.assertNotIn("\n  pull_request:\n", self.workflow)

    def test_dispatch_job_is_observable_not_silently_skipped_on_missing_proxy_var(self) -> None:
        self.assertNotIn("if: vars.PROXY_URL != ''", self.workflow)
        self.assertNotIn("PROXY_URL", self.workflow)
        self.assertIn("TOOLCHAIN_UNAVAILABLE", self.workflow)
        self.assertIn("NO_DISPATCH_EVENT", self.workflow)

    def test_automatic_ci_dispatch_requires_explicit_control_plane_enablement(self) -> None:
        self.assertIn("AGENT_DISPATCH_AUTOMATION_ENABLED", self.workflow)
        self.assertIn("AUTOMATION_NOT_ENABLED", self.workflow)

    def test_workflow_uses_keyless_wif_and_discovers_canonical_service(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("vars.WIF_PROVIDER", self.workflow)
        self.assertIn("vars.WIF_SERVICE_ACCOUNT", self.workflow)
        self.assertIn("gcloud run services describe aegis-platform", self.workflow)
        self.assertIn("--region us-central1", self.workflow)
        self.assertIn("--project", self.workflow)

    def test_platform_key_is_brokered_at_execution_time_and_masked(self) -> None:
        self.assertIn("gcloud secrets versions access latest", self.workflow)
        self.assertIn("--secret=platform-api-key", self.workflow)
        self.assertIn("::add-mask::", self.workflow)
        self.assertNotIn("secrets.PLATFORM_API_KEY", self.workflow)

    def test_external_events_require_trusted_actor_and_explicit_agent_intent(self) -> None:
        self.assertIn("OWNER|MEMBER|COLLABORATOR", self.workflow)
        self.assertIn("PR_AUTHOR_ASSOCIATION", self.workflow)
        self.assertIn("ISSUE_AUTHOR_ASSOCIATION", self.workflow)
        self.assertIn("COMMENT_AUTHOR_ASSOCIATION", self.workflow)
        self.assertIn("aegis-agent", self.workflow)
        self.assertIn("@aegis-agent", self.workflow)

    def test_ci_dispatch_is_restricted_to_main_push_of_this_repository(self) -> None:
        self.assertIn("WF_EVENT", self.workflow)
        self.assertIn("WF_HEAD_REPOSITORY", self.workflow)
        self.assertIn("WF_BRANCH", self.workflow)
        self.assertIn('"push"', self.workflow)
        self.assertIn('"main"', self.workflow)
        self.assertIn("GITHUB_REPOSITORY", self.workflow)

    def test_http_dispatch_has_bounded_failure_and_response_validation(self) -> None:
        self.assertIn("--fail-with-body", self.workflow)
        self.assertIn("--connect-timeout", self.workflow)
        self.assertIn("--max-time", self.workflow)
        self.assertIn("x-api-key", self.workflow)
        self.assertIn("jq -e", self.workflow)
        self.assertIn("is_valid", self.workflow)
        self.assertIn("DISPATCH_RECEIPT", self.workflow)
        self.assertIn("actions/upload-artifact@v4", self.workflow)
        self.assertNotIn(".output | .[0:500]", self.workflow)

    def test_outer_authority_boundary_is_production_entrypoint(self) -> None:
        self.assertIn("AUTHORITY_UNAVAILABLE", self.boundary)
        self.assertIn("hmac.compare_digest", self.boundary)
        self.assertIn("COPY vertex/authority_boundary.py /app/authority_boundary.py", self.dockerfile)
        self.assertIn("COPY vertex/runtime.py /app/runtime.py", self.dockerfile)
        self.assertIn('CMD ["python", "runtime.py"]', self.dockerfile)

    def test_canonical_deploy_binds_platform_key_to_agent_service(self) -> None:
        self.assertIn("aegis-platform", self.deploy)
        self.assertIn("--region=us-central1", self.deploy)
        self.assertIn("PLATFORM_API_KEY=platform-api-key:latest", self.deploy)


if __name__ == "__main__":
    unittest.main()
