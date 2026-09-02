#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "agent-dispatch.yml"
DOCKERFILE = ROOT / "vertex" / "Dockerfile"
RUNTIME = ROOT / "vertex" / "runtime.py"
BOUNDARY = ROOT / "vertex" / "authority_boundary.py"
AUTH_ACTION_SHA = "c200f3691d83b41bf9bbd8638997a462592937ed"


class AgentDispatchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.boundary = BOUNDARY.read_text(encoding="utf-8")

    def test_real_constitutional_workflow_is_the_ci_source(self) -> None:
        self.assertIn('workflows: ["⊕ AEGIS-Ω Constitutional Automaton"]', self.workflow)
        self.assertNotIn('workflows: ["CI"]', self.workflow)

    def test_missing_proxy_cannot_skip_the_entire_job(self) -> None:
        self.assertNotIn("if: vars.PROXY_URL != ''", self.workflow)
        self.assertIn("Agent Dispatch Admission", self.workflow)
        self.assertIn("TOOLCHAIN_UNAVAILABLE", self.workflow)
        self.assertIn("AUTOMATION_NOT_ENABLED", self.workflow)

    def test_pr_metadata_uses_trusted_default_branch_workflow(self) -> None:
        self.assertIn("pull_request_target:", self.workflow)
        self.assertNotIn("\n  pull_request:\n", self.workflow)
        self.assertIn("github.event.repository.default_branch", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_external_effect_uses_source_pinned_keyless_wif_and_execution_time_secret_brokerage(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn(f"google-github-actions/auth@{AUTH_ACTION_SHA}", self.workflow)
        self.assertNotIn("google-github-actions/auth@v2", self.workflow)
        self.assertIn("vars.WIF_PROVIDER", self.workflow)
        self.assertIn("vars.WIF_SERVICE_ACCOUNT", self.workflow)
        self.assertIn("gcloud run services describe aegis-platform", self.workflow)
        self.assertIn("--region us-central1", self.workflow)
        self.assertIn("gcloud secrets versions access latest", self.workflow)
        self.assertIn("--secret=platform-api-key", self.workflow)
        self.assertIn("::add-mask::", self.workflow)

    def test_network_effect_is_bounded_and_response_checked(self) -> None:
        for token in ("--fail-with-body", "--retry 3", "--connect-timeout 5", "--max-time 30", "--max-filesize 65536"):
            self.assertIn(token, self.workflow)
        self.assertIn("x-api-key", self.workflow)
        self.assertIn("jq -e", self.workflow)
        self.assertIn("is_valid", self.workflow)

    def test_receipt_is_emitted_even_when_effect_is_deferred(self) -> None:
        self.assertIn("Emit decision and effect receipt", self.workflow)
        self.assertIn("if: always()", self.workflow)
        self.assertIn("AGENT_DISPATCH_RECEIPT.json", self.workflow)
        self.assertIn("semantic_truth_proven", self.workflow)
        self.assertIn("Upload dispatch receipt", self.workflow)

    def test_paid_routes_are_fail_closed_before_fastapi(self) -> None:
        self.assertIn("AUTHORITY_UNAVAILABLE", self.boundary)
        self.assertIn("hmac.compare_digest", self.boundary)
        self.assertIn("AuthorityBoundary(inner_app)", self.runtime)
        self.assertIn("COPY vertex/authority_boundary.py /app/authority_boundary.py", self.dockerfile)
        self.assertIn("COPY vertex/runtime.py /app/runtime.py", self.dockerfile)
        self.assertIn('CMD ["python", "runtime.py"]', self.dockerfile)


if __name__ == "__main__":
    unittest.main()
