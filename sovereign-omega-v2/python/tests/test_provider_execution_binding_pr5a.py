#!/usr/bin/env python3
"""PR-5A falsifiers for serialized provider execution evidence binding."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.provider_execution_binding import (  # noqa: E402
    PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND,
    ProviderExecutionBindingError,
    ProviderExecutionEvidenceBinding,
    verify_provider_execution_binding,
)
from harness.sdk.effect_adapters import EffectWitness  # noqa: E402
from harness.sdk.transition_receipts import EffectReceipt  # noqa: E402

H = lambda c: c * 64


class ProviderExecutionBindingPR5ATests(TestCase):
    def payload(self):
        return {
            "binding_kind": PROVIDER_EXECUTION_EVIDENCE_BINDING_KIND,
            "provider": "openai",
            "request_id": "request-pr5a-0001",
            "provider_operation_id": "op-pr5a-0001",
            "response_digest": H("2"),
            "work_order_digest": H("3"),
            "authority_receipt_root": H("4"),
            "transition_id": H("5"),
            "execution_instance_id": "exec-pr5a-0001",
            "expected_parent_state_root": H("1"),
            "grants_authority": False,
        }

    def test_exact_serialized_binding_is_valid_and_non_authoritative(self):
        binding = ProviderExecutionEvidenceBinding.from_mapping(self.payload())
        self.assertFalse(binding.grants_authority)
        self.assertRegex(binding.root, r"^[0-9a-f]{64}$")
        self.assertTrue(verify_provider_execution_binding(binding, **self.payload()))
        self.assertFalse(isinstance(binding, EffectWitness))
        self.assertFalse(isinstance(binding, EffectReceipt))

    def test_root_is_deterministic(self):
        first = ProviderExecutionEvidenceBinding.from_mapping(self.payload())
        second = ProviderExecutionEvidenceBinding.from_mapping(json.loads(json.dumps(self.payload())))
        self.assertEqual(first.root, second.root)

    def test_extra_or_missing_field_is_rejected(self):
        extra = {**self.payload(), "untrusted": True}
        with self.assertRaises(ProviderExecutionBindingError):
            ProviderExecutionEvidenceBinding.from_mapping(extra)
        missing = self.payload(); missing.pop("authority_receipt_root")
        with self.assertRaises(ProviderExecutionBindingError):
            ProviderExecutionEvidenceBinding.from_mapping(missing)

    def test_authority_promotion_is_rejected(self):
        with self.assertRaises(ProviderExecutionBindingError):
            ProviderExecutionEvidenceBinding.from_mapping({**self.payload(), "grants_authority": True})

    def test_python_provider_evidence_shape_cannot_be_promoted(self):
        raw_provider_evidence = {
            "provider": "openai",
            "capability": "inference.run",
            "request_id": "request-pr5a-0001",
            "provider_operation_id": "op-pr5a-0001",
            "response_digest": H("2"),
            "status": "succeeded",
            "input_tokens": 1,
            "output_tokens": 1,
            "external_reference": None,
            "grants_authority": False,
        }
        with self.assertRaises(ProviderExecutionBindingError):
            ProviderExecutionEvidenceBinding.from_mapping(raw_provider_evidence)

    def test_malformed_hashes_and_ids_are_rejected(self):
        for key in (
            "response_digest", "work_order_digest", "authority_receipt_root",
            "transition_id", "expected_parent_state_root",
        ):
            with self.subTest(key=key):
                with self.assertRaises(ProviderExecutionBindingError):
                    ProviderExecutionEvidenceBinding.from_mapping({**self.payload(), key: "bad"})
        with self.assertRaises(ProviderExecutionBindingError):
            ProviderExecutionEvidenceBinding.from_mapping({**self.payload(), "provider": "open ai"})

    def test_every_bound_field_mismatch_fails_closed(self):
        binding = ProviderExecutionEvidenceBinding.from_mapping(self.payload())
        variants = {
            "provider": "anthropic",
            "request_id": "request-other",
            "provider_operation_id": "op-other",
            "response_digest": H("6"),
            "work_order_digest": H("7"),
            "authority_receipt_root": H("8"),
            "transition_id": H("9"),
            "execution_instance_id": "exec-other",
            "expected_parent_state_root": H("a"),
        }
        for key, value in variants.items():
            expected = self.payload(); expected[key] = value
            with self.subTest(key=key):
                self.assertFalse(verify_provider_execution_binding(binding, **expected))

    def test_binding_kind_is_nominal(self):
        with self.assertRaises(ProviderExecutionBindingError):
            ProviderExecutionEvidenceBinding.from_mapping({**self.payload(), "binding_kind": "EFFECT_RECEIPT_V1"})


if __name__ == "__main__":
    main()
