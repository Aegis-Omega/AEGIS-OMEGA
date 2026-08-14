from __future__ import annotations

from pathlib import Path
import sys
import unittest

FRONTIER_DIR = Path(__file__).resolve().parents[1] / "frontier"
sys.path.insert(0, str(FRONTIER_DIR))

from http_transport import CredentialMaterial, HTTPResponse  # noqa: E402
from managed_transport import ManagedProviderResult  # noqa: E402
from mesh import FrontierConnectionSpec, FrontierMeshError, build_frontier_router  # noqa: E402


class FakeCredentials:
    def resolve(self, reference):
        return CredentialMaterial(kind="bearer", value="runtime-only")


class FakeHTTP:
    def send(self, request):
        return HTTPResponse(
            status=200,
            headers={"x-request-id": "req-provider"},
            body=b'{"id":"provider-1","usage":{"input_tokens":1,"output_tokens":1}}',
        )


class FakeManaged:
    def invoke(self, provider, payload, request_id):
        return ManagedProviderResult(
            operation_id=f"{provider}-1",
            response={"ok": True},
            input_tokens=1,
            output_tokens=1,
        )


class FrontierMeshTests(unittest.TestCase):
    def test_builds_http_and_managed_transports_into_one_router(self):
        router = build_frontier_router(
            connections=(
                FrontierConnectionSpec(
                    provider="openai",
                    protocol="openai-responses",
                    endpoint="https://api.openai.com",
                    auth_reference="secret://openai/aegisomega",
                ),
                FrontierConnectionSpec(
                    provider="google-vertex",
                    protocol="managed-sdk",
                    endpoint="managed://google-vertex",
                    auth_reference="identity://google/aegisomega",
                ),
            ),
            credential_resolver=FakeCredentials(),
            http_executor=FakeHTTP(),
            managed_invokers={"google-vertex": FakeManaged()},
        )
        self.assertEqual(router.registered_providers(), ("google-vertex", "openai"))

    def test_duplicate_provider_connection_is_rejected(self):
        spec = FrontierConnectionSpec(
            provider="openai",
            protocol="openai-responses",
            endpoint="https://api.openai.com",
            auth_reference="secret://openai/aegisomega",
        )
        with self.assertRaises(FrontierMeshError):
            build_frontier_router(
                connections=(spec, spec),
                credential_resolver=FakeCredentials(),
                http_executor=FakeHTTP(),
                managed_invokers={},
            )

    def test_managed_provider_requires_runtime_invoker(self):
        with self.assertRaises(FrontierMeshError):
            build_frontier_router(
                connections=(FrontierConnectionSpec(
                    provider="aws-bedrock",
                    protocol="managed-sdk",
                    endpoint="managed://aws-bedrock",
                    auth_reference="identity://aws/aegisomega",
                ),),
                credential_resolver=FakeCredentials(),
                http_executor=FakeHTTP(),
                managed_invokers={},
            )

    def test_http_connection_requires_http_executor(self):
        with self.assertRaises(FrontierMeshError):
            build_frontier_router(
                connections=(FrontierConnectionSpec(
                    provider="openai",
                    protocol="openai-responses",
                    endpoint="https://api.openai.com",
                    auth_reference="secret://openai/aegisomega",
                ),),
                credential_resolver=FakeCredentials(),
                http_executor=None,
                managed_invokers={},
            )

    def test_unknown_connection_protocol_is_rejected(self):
        with self.assertRaises(FrontierMeshError):
            build_frontier_router(
                connections=(FrontierConnectionSpec(
                    provider="openai",
                    protocol="magic-provider-bypass",
                    endpoint="https://api.openai.com",
                    auth_reference="secret://openai/aegisomega",
                ),),
                credential_resolver=FakeCredentials(),
                http_executor=FakeHTTP(),
                managed_invokers={},
            )


if __name__ == "__main__":
    unittest.main()
