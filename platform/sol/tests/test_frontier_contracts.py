from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import jsonschema

SOL_DIR = Path(__file__).resolve().parents[1]
FRONTIER_DIR = SOL_DIR / "frontier"
CONTRACTS_DIR = SOL_DIR / "contracts"
sys.path.insert(0, str(FRONTIER_DIR))

from providers import FRONTIER_PROVIDERS  # noqa: E402


class FrontierContractTests(unittest.TestCase):
    def load(self, name: str):
        return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))

    def test_frontier_provider_ids_are_admitted_by_all_execution_contracts(self):
        frontier = {provider.id for provider in FRONTIER_PROVIDERS}
        for name in (
            "execution-request.v1.schema.json",
            "execution-result.v1.schema.json",
            "proof-carrying-work-order.v1.schema.json",
        ):
            schema = self.load(name)
            admitted = set(schema["$defs"]["provider"]["enum"])
            self.assertTrue(frontier <= admitted, f"{name} is missing {sorted(frontier - admitted)}")

    def test_platform_registry_contains_every_frontier_provider(self):
        registry = self.load("platform-registry.v1.json")
        ids = {entry["id"] for entry in registry["platforms"]}
        frontier = {provider.id for provider in FRONTIER_PROVIDERS}
        self.assertTrue(frontier <= ids)
        self.assertEqual(registry["authority_root"], "automaton-3")
        self.assertEqual(registry["default_policy"], "deny")

    def test_frontier_provider_default_consequence_matches_platform_registry(self):
        registry = self.load("platform-registry.v1.json")
        by_id = {entry["id"]: entry for entry in registry["platforms"]}
        for provider in FRONTIER_PROVIDERS:
            self.assertEqual(
                by_id[provider.id]["default_consequence_class"],
                provider.default_consequence_class,
                provider.id,
            )

    def test_execution_result_cannot_claim_provider_authority(self):
        schema = self.load("execution-result.v1.schema.json")
        self.assertEqual(schema["properties"]["grants_authority"], {"const": False})

    def test_d3_inference_request_requires_work_order_approval_and_budget_envelope(self):
        schema = self.load("execution-request.v1.schema.json")
        request = {
            "schema_version": "1.0.0",
            "request_id": "0b396805-6cc0-4d8c-bb31-f3327967e9ca",
            "actor": {"id": "operator:tarik", "type": "operator"},
            "agent": {"id": "sol-operator", "runtime": "openai", "model": "configured-model"},
            "provider": "openai",
            "capability": "inference.run",
            "consequence_class": "D3",
            "target": "model://configured-deployment",
            "arguments_digest": "0" * 64,
            "expected_parent_state_root": "1" * 64,
            "lease_generation": 1,
            "idempotency_key": "idem-00000001",
            "work_order_digest": "2" * 64,
            "max_cost_microusd": 500000,
            "max_input_tokens": 1000,
            "max_output_tokens": 1000,
            "operator_approval_reference": "approval://operator/1",
            "requested_at": "2026-08-14T17:00:00Z"
        }
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(request)

    def test_d3_request_without_work_order_is_invalid(self):
        schema = self.load("execution-request.v1.schema.json")
        request = {
            "schema_version": "1.0.0",
            "request_id": "0b396805-6cc0-4d8c-bb31-f3327967e9ca",
            "actor": {"id": "operator:tarik", "type": "operator"},
            "agent": {"id": "sol-operator", "runtime": "openai", "model": "configured-model"},
            "provider": "openai",
            "capability": "inference.run",
            "consequence_class": "D3",
            "target": "model://configured-deployment",
            "arguments_digest": "0" * 64,
            "expected_parent_state_root": "1" * 64,
            "lease_generation": 1,
            "idempotency_key": "idem-00000001",
            "operator_approval_reference": "approval://operator/1",
            "requested_at": "2026-08-14T17:00:00Z"
        }
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(request)


if __name__ == "__main__":
    unittest.main()
