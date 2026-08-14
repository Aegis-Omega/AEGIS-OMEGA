from __future__ import annotations

from pathlib import Path
import sys
import unittest

FRONTIER_DIR = Path(__file__).resolve().parents[1] / "frontier"
sys.path.insert(0, str(FRONTIER_DIR))

from a2a import A2AAgentEndpoint, A2ATaskEnvelope, A2AError, verify_a2a_task  # noqa: E402
from mcp import MCPError, RemoteMCPServer, verify_mcp_server  # noqa: E402
from router import GovernedProviderRouter, ProviderEvidence, ProviderInvocation, RouterError  # noqa: E402
from work_order import ProofCarryingWorkOrder  # noqa: E402

HEX0 = "0" * 64
HEX1 = "1" * 64
HEX2 = "2" * 64


class FakeTransport:
    provider = "openai"

    def __init__(self):
        self.calls = 0

    def invoke(self, invocation):
        self.calls += 1
        return ProviderEvidence(
            provider=invocation.provider,
            capability=invocation.capability,
            request_id=invocation.request_id,
            provider_operation_id=f"op-{self.calls}",
            response_digest=HEX2,
            status="SUCCEEDED",
            input_tokens=10,
            output_tokens=20,
            external_reference="provider://openai/op",
        )


def valid_order(**overrides):
    values = dict(
        work_order_id="wo-1",
        request_id="req-1",
        provider="openai",
        capability="inference.run",
        consequence_class="D3",
        arguments_digest=HEX0,
        expected_parent_state_root=HEX1,
        idempotency_key="idem-0001",
        max_cost_microusd=500000,
        max_input_tokens=1000,
        max_output_tokens=1000,
        evidence_references=("receipt://admission/1",),
        operator_approval_reference="approval://operator/1",
        secret_references=("secret://openai/aegisomega",),
        issued_sequence=1,
    )
    values.update(overrides)
    return ProofCarryingWorkOrder(**values)


def invocation(**overrides):
    values = dict(
        request_id="req-1",
        provider="openai",
        capability="inference.run",
        consequence_class="D3",
        arguments_digest=HEX0,
        expected_parent_state_root=HEX1,
        idempotency_key="idem-0001",
        max_cost_microusd=100000,
        max_input_tokens=500,
        max_output_tokens=500,
        work_order=valid_order(),
    )
    values.update(overrides)
    return ProviderInvocation(**values)


class MCPTests(unittest.TestCase):
    def test_mcp_requires_explicit_allowlist(self):
        with self.assertRaises(MCPError):
            verify_mcp_server(RemoteMCPServer(
                name="github",
                url="https://api.githubcopilot.com/mcp/",
                allowed_tools=(),
                approval_policy="aegis",
                auth_reference="oauth://github/copilot",
            ))

    def test_mcp_rejects_wildcard_allowlist(self):
        with self.assertRaises(MCPError):
            verify_mcp_server(RemoteMCPServer(
                name="unsafe",
                url="https://example.com/mcp",
                allowed_tools=("*",),
                approval_policy="aegis",
                auth_reference="oauth://example",
            ))

    def test_mcp_accepts_https_with_scoped_tools_and_auth_reference(self):
        server = verify_mcp_server(RemoteMCPServer(
            name="github",
            url="https://api.githubcopilot.com/mcp/",
            allowed_tools=("repos.read", "pull_requests.read"),
            approval_policy="aegis",
            auth_reference="oauth://github/copilot",
        ))
        self.assertEqual(server.transport, "streamable-http")


class A2ATests(unittest.TestCase):
    def endpoint(self):
        return A2AAgentEndpoint(
            name="gemini-specialist",
            agent_card_url="https://agents.example/.well-known/agent-card.json",
            service_url="https://agents.example/a2a",
            auth_reference="identity://google/workload",
            allowed_skills=("research",),
        )

    def task(self):
        return A2ATaskEnvelope(
            task_id="task-1",
            execution_id="exec-1",
            sender="aegis:sol",
            recipient="gemini-specialist",
            skill="research",
            input_digest=HEX0,
            stream_owner="operator:tarik",
            stream_generation=3,
        )

    def test_a2a_task_requires_current_stream_owner(self):
        with self.assertRaises(A2AError):
            verify_a2a_task(self.endpoint(), self.task(), expected_stream_owner="agent:wrong", expected_generation=3)

    def test_a2a_task_is_bound_to_declared_skill_and_protocol_v1(self):
        verified = verify_a2a_task(
            self.endpoint(),
            self.task(),
            expected_stream_owner="operator:tarik",
            expected_generation=3,
        )
        self.assertEqual(verified.protocol_version, "1.0.0")


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.router = GovernedProviderRouter([self.transport])

    def test_unknown_provider_is_denied(self):
        with self.assertRaises(RouterError):
            self.router.invoke(invocation(provider="unknown", work_order=None, max_cost_microusd=0, consequence_class="D0"))

    def test_undeclared_capability_is_denied(self):
        with self.assertRaises(RouterError):
            self.router.invoke(invocation(capability="authority.grant"))

    def test_cost_incurring_work_requires_work_order(self):
        with self.assertRaises(RouterError):
            self.router.invoke(invocation(work_order=None))

    def test_work_order_must_bind_full_budget_and_parent_envelope(self):
        with self.assertRaises(RouterError):
            self.router.invoke(invocation(work_order=valid_order(expected_parent_state_root=HEX2)))

    def test_valid_d3_work_order_allows_transport_but_evidence_never_grants_authority(self):
        result = self.router.invoke(invocation())
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertFalse(result.grants_authority)
        self.assertEqual(self.transport.calls, 1)

    def test_idempotent_duplicate_collapses_to_one_provider_call(self):
        first = self.router.invoke(invocation())
        second = self.router.invoke(invocation())
        self.assertEqual(first, second)
        self.assertEqual(self.transport.calls, 1)

    def test_transport_provider_must_match_registration(self):
        class WrongTransport(FakeTransport):
            provider = "anthropic"

        router = GovernedProviderRouter([WrongTransport()])
        with self.assertRaises(RouterError):
            router.invoke(invocation())


if __name__ == "__main__":
    unittest.main()
