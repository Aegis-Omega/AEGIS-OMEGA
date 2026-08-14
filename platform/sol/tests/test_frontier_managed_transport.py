from __future__ import annotations

from pathlib import Path
import sys
import unittest

FRONTIER_DIR = Path(__file__).resolve().parents[1] / "frontier"
sys.path.insert(0, str(FRONTIER_DIR))

from managed_transport import (  # noqa: E402
    ManagedProviderResult,
    ManagedProviderTransport,
    ManagedTransportError,
)
from router import ProviderInvocation, canonical_payload_digest  # noqa: E402

HEX1 = "1" * 64


def invocation(provider: str):
    payload = {"model": "configured-deployment", "messages": [{"role": "user", "content": "hello"}]}
    return ProviderInvocation(
        request_id=f"req-{provider}",
        provider=provider,
        capability="inference.run",
        consequence_class="D0",
        arguments_digest=canonical_payload_digest(payload),
        expected_parent_state_root=HEX1,
        idempotency_key=f"idem-{provider}-0001",
        max_cost_microusd=0,
        max_input_tokens=100,
        max_output_tokens=100,
        payload=payload,
    )


class FakeInvoker:
    def __init__(self):
        self.calls = []

    def invoke(self, provider, payload, request_id):
        self.calls.append((provider, payload, request_id))
        return ManagedProviderResult(
            operation_id=f"{provider}-op-1",
            response={"provider": provider, "answer": "ok"},
            input_tokens=12,
            output_tokens=8,
            external_reference=f"managed://{provider}/op-1",
        )


class ManagedProviderTransportTests(unittest.TestCase):
    def test_vertex_managed_transport_returns_non_authoritative_evidence(self):
        invoker = FakeInvoker()
        transport = ManagedProviderTransport("google-vertex", invoker)
        evidence = transport.invoke(invocation("google-vertex"))
        self.assertEqual(evidence.provider, "google-vertex")
        self.assertFalse(evidence.grants_authority)
        self.assertEqual(invoker.calls[0][0], "google-vertex")

    def test_foundry_managed_transport_is_supported(self):
        evidence = ManagedProviderTransport("microsoft-foundry", FakeInvoker()).invoke(invocation("microsoft-foundry"))
        self.assertEqual(evidence.provider_operation_id, "microsoft-foundry-op-1")

    def test_bedrock_managed_transport_is_supported(self):
        evidence = ManagedProviderTransport("aws-bedrock", FakeInvoker()).invoke(invocation("aws-bedrock"))
        self.assertEqual(evidence.provider_operation_id, "aws-bedrock-op-1")

    def test_transport_rejects_non_managed_provider(self):
        with self.assertRaises(ManagedTransportError):
            ManagedProviderTransport("openai", FakeInvoker())

    def test_transport_rejects_provider_mismatch(self):
        transport = ManagedProviderTransport("google-vertex", FakeInvoker())
        with self.assertRaises(ManagedTransportError):
            transport.invoke(invocation("microsoft-foundry"))

    def test_transport_requires_payload(self):
        inv = invocation("google-vertex")
        inv = ProviderInvocation(
            request_id=inv.request_id,
            provider=inv.provider,
            capability=inv.capability,
            consequence_class=inv.consequence_class,
            arguments_digest=inv.arguments_digest,
            expected_parent_state_root=inv.expected_parent_state_root,
            idempotency_key=inv.idempotency_key,
            max_cost_microusd=inv.max_cost_microusd,
            max_input_tokens=inv.max_input_tokens,
            max_output_tokens=inv.max_output_tokens,
            payload=None,
        )
        with self.assertRaises(ManagedTransportError):
            ManagedProviderTransport("google-vertex", FakeInvoker()).invoke(inv)


if __name__ == "__main__":
    unittest.main()
