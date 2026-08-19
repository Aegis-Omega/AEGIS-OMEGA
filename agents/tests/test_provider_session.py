from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.organism import OrganismStore, OrganizationOrganism
from harness.sdk.provider_session import build_provider_session
from harness.sdk.sovereign_execution import ExecutionIdentityEnvelope, git_head


BASE = {
    "provider": "openai",
    "model": "gpt-5.6-sol",
    "session": "cross-provider-001",
    "action_class": "D0",
    "authority_domain": "organism:read",
    "requested_capability": "mcp.organism.status",
    "tool": "aegis_organism_status",
    "target": ".aegis/runtime/organism.json",
    "mutation_target": ".",
    "action": {"operation": "read-organism-status"},
}


class ProviderSessionBootstrapTests(unittest.TestCase):
    def build(self, **changes):
        payload = dict(BASE)
        payload.update(changes)
        return build_provider_session(payload)

    def test_bootstrap_binds_live_exact_head_and_valid_identity(self):
        result = self.build()
        identity = ExecutionIdentityEnvelope(**result["identity"])
        self.assertEqual(identity.source_commit, git_head(Path(__file__).resolve().parents[2]))
        self.assertEqual(identity.root, result["identity_root"])
        self.assertEqual(result["authority"], "IDENTITY_ONLY_NOT_AUTHORIZATION")

    def test_provider_model_and_session_are_bound(self):
        result = self.build(provider="gemini", model="gemini-3.5-flash", session="g-001")
        identity = result["identity"]
        self.assertEqual(identity["actor_identity"], "provider:gemini")
        self.assertEqual(identity["model_identity"], "model:gemini-3.5-flash")
        self.assertEqual(identity["session_identity"], "session:g-001")

    def test_same_state_and_action_are_deterministic(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first["identity_root"], second["identity_root"])
        self.assertEqual(first["identity"]["deterministic_nonce"], second["identity"]["deterministic_nonce"])

    def test_action_change_changes_identity(self):
        first = self.build()
        second = self.build(action={"operation": "read-organism-status", "scope": "different"})
        self.assertNotEqual(first["identity_root"], second["identity_root"])
        self.assertNotEqual(first["identity"]["action_digest"], second["identity"]["action_digest"])

    def test_organism_state_root_is_bound(self):
        with tempfile.TemporaryDirectory() as td:
            store_path = Path(td) / "organism.json"
            with patch.dict(os.environ, {"AEGIS_ORGANISM_STORE": str(store_path)}, clear=False):
                org = OrganizationOrganism(OrganismStore(store_path))
                org.submit("work-1", "research_request", {"topic": "continuity"}, consequence_class="D1")
                expected = org.store.state_root()
                result = self.build()
                self.assertEqual(result["state_root"], expected)
                self.assertEqual(result["identity"]["expected_pre_state"], expected)
                self.assertEqual(result["identity"]["parent_state_root"], expected)

    def test_unmapped_capability_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "UNMAPPED_CAPABILITY"):
            self.build(requested_capability="mcp.does.not.exist")

    def test_unsafe_provider_identity_is_rejected(self):
        with self.assertRaises(Exception):
            self.build(provider="bad provider")

    def test_bootstrap_never_creates_approval_or_authority(self):
        with patch.dict(os.environ, {}, clear=False):
            result = self.build()
        self.assertEqual(result["identity"]["approval_reference"], "NONE")
        self.assertEqual(result["identity"]["observed_authority"], "0.000000")
        self.assertEqual(result["authority"], "IDENTITY_ONLY_NOT_AUTHORIZATION")


if __name__ == "__main__":
    unittest.main()
