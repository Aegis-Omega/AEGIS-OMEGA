from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

FRONTIER_DIR = Path(__file__).resolve().parents[1] / "frontier"
sys.path.insert(0, str(FRONTIER_DIR))

from http_transport import (  # noqa: E402
    CredentialMaterial,
    HTTPResponse,
    ProviderConnection,
    ProviderHTTPTransport,
    TransportError,
)
from router import ProviderInvocation, canonical_payload_digest  # noqa: E402

HEX1 = "1" * 64


class FakeCredentialResolver:
    def resolve(self, reference: str) -> CredentialMaterial:
        if reference == "secret://openai/aegisomega":
            return CredentialMaterial(kind="bearer", value="runtime-secret")
        if reference == "secret://anthropic/aegisomega":
            return CredentialMaterial(kind="api-key", value="runtime-anthropic-secret")
        raise KeyError(reference)


class FakeExecutor:
    def __init__(self, status=200, body=None, headers=None):
        self.status = status
        self.body = body or {"id": "provider-op-1", "usage": {"input_tokens": 9, "output_tokens": 11}}
        self.headers = headers or {"x-request-id": "request-header-1"}
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        return HTTPResponse(
            status=self.status,
            headers=self.headers,
            body=json.dumps(self.body, sort_keys=True).encode("utf-8"),
        )


def invocation(provider="openai"):
    payload = {"model": "frontier-test-model", "input": "hello"}
    return ProviderInvocation(
        request_id="req-1",
        provider=provider,
        capability="inference.run",
        target=f"model://{provider}/frontier-test-model",
        consequence_class="D0",
        arguments_digest=canonical_payload_digest(payload),
        expected_parent_state_root=HEX1,
        idempotency_key="idem-0001",
        max_cost_microusd=0,
        max_input_tokens=100,
        max_output_tokens=100,
        work_order=None,
        payload=payload,
    )


class ProviderHTTPTransportTests(unittest.TestCase):
    def test_openai_responses_transport_builds_server_side_bearer_request(self):
        executor = FakeExecutor(body={"id": "resp_1", "usage": {"input_tokens": 7, "output_tokens": 5}})
        transport = ProviderHTTPTransport(
            ProviderConnection(
                provider="openai",
                protocol="openai-responses",
                base_url="https://api.openai.com",
                auth_reference="secret://openai/aegisomega",
            ),
            FakeCredentialResolver(),
            executor,
        )
        evidence = transport.invoke(invocation())
        request = executor.requests[0]
        self.assertEqual(request.url, "https://api.openai.com/v1/responses")
        self.assertEqual(request.headers["authorization"], "Bearer runtime-secret")
        self.assertNotIn("runtime-secret", repr(evidence))
        self.assertEqual(evidence.provider_operation_id, "resp_1")
        self.assertFalse(evidence.grants_authority)

    def test_anthropic_messages_transport_uses_api_key_header_and_version(self):
        executor = FakeExecutor(body={"id": "msg_1", "usage": {"input_tokens": 3, "output_tokens": 4}})
        transport = ProviderHTTPTransport(
            ProviderConnection(
                provider="anthropic",
                protocol="anthropic-messages",
                base_url="https://api.anthropic.com",
                auth_reference="secret://anthropic/aegisomega",
            ),
            FakeCredentialResolver(),
            executor,
        )
        evidence = transport.invoke(invocation(provider="anthropic"))
        request = executor.requests[0]
        self.assertEqual(request.url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.headers["x-api-key"], "runtime-anthropic-secret")
        self.assertIn("anthropic-version", request.headers)
        self.assertNotIn("runtime-anthropic-secret", repr(evidence))

    def test_openai_compatible_transport_uses_configured_endpoint(self):
        executor = FakeExecutor(body={"id": "chatcmpl_1", "usage": {"prompt_tokens": 4, "completion_tokens": 6}})
        transport = ProviderHTTPTransport(
            ProviderConnection(
                provider="xai",
                protocol="openai-compatible-chat",
                base_url="https://api.x.ai/v1",
                auth_reference="secret://xai/aegisomega",
            ),
            lambda reference: CredentialMaterial(kind="bearer", value="xai-runtime-secret"),
            executor,
        )
        evidence = transport.invoke(invocation(provider="xai"))
        self.assertEqual(executor.requests[0].url, "https://api.x.ai/v1/chat/completions")
        self.assertEqual(evidence.input_tokens, 4)
        self.assertEqual(evidence.output_tokens, 6)

    def test_transport_rejects_provider_mismatch(self):
        transport = ProviderHTTPTransport(
            ProviderConnection(
                provider="openai",
                protocol="openai-responses",
                base_url="https://api.openai.com",
                auth_reference="secret://openai/aegisomega",
            ),
            FakeCredentialResolver(),
            FakeExecutor(),
        )
        with self.assertRaises(TransportError):
            transport.invoke(invocation(provider="anthropic"))

    def test_transport_fails_closed_on_non_success_response(self):
        transport = ProviderHTTPTransport(
            ProviderConnection(
                provider="openai",
                protocol="openai-responses",
                base_url="https://api.openai.com",
                auth_reference="secret://openai/aegisomega",
            ),
            FakeCredentialResolver(),
            FakeExecutor(status=429, body={"error": {"message": "rate limit"}}),
        )
        with self.assertRaises(TransportError):
            transport.invoke(invocation())

    def test_connection_rejects_inline_auth_material(self):
        with self.assertRaises(TransportError):
            ProviderHTTPTransport(
                ProviderConnection(
                    provider="openai",
                    protocol="openai-responses",
                    base_url="https://api.openai.com",
                    auth_reference="sk-inline-forbidden",
                ),
                FakeCredentialResolver(),
                FakeExecutor(),
            )


if __name__ == "__main__":
    unittest.main()
