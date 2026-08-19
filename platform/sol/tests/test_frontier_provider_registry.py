from __future__ import annotations

from pathlib import Path
import sys
import unittest

FRONTIER_DIR = Path(__file__).resolve().parents[1] / "frontier"
sys.path.insert(0, str(FRONTIER_DIR))

from providers import FRONTIER_PROVIDERS, ProviderRegistryError, get_provider  # noqa: E402

EXPECTED = {
    "openai",
    "anthropic",
    "google-vertex",
    "microsoft-foundry",
    "aws-bedrock",
    "vercel-ai-gateway",
    "xai",
    "mistral",
    "deepseek",
    "qwen-dashscope",
    "nvidia-nim",
    "huggingface",
}


class FrontierProviderRegistryTests(unittest.TestCase):
    def test_expected_frontier_provider_set_is_registered(self):
        self.assertEqual({provider.id for provider in FRONTIER_PROVIDERS}, EXPECTED)

    def test_provider_ids_are_unique(self):
        ids = [provider.id for provider in FRONTIER_PROVIDERS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_unknown_provider_is_denied(self):
        with self.assertRaises(ProviderRegistryError):
            get_provider("unknown-frontier-provider")

    def test_descriptors_contain_no_inline_credentials(self):
        for provider in FRONTIER_PROVIDERS:
            self.assertTrue(provider.auth_reference_schemes)
            for scheme in provider.auth_reference_schemes:
                self.assertTrue(scheme.endswith("://"))
            serialized = repr(provider).lower()
            self.assertNotIn("sk-", serialized)
            self.assertNotIn("bearer ", serialized)

    def test_all_model_providers_declare_inference_capability_and_streaming(self):
        for provider in FRONTIER_PROVIDERS:
            self.assertIn("inference.run", provider.capabilities)
            self.assertTrue(provider.streaming_modes)

    def test_openai_exposes_responses_and_remote_mcp(self):
        provider = get_provider("openai")
        self.assertIn("responses-api", provider.native_protocols)
        self.assertIn("mcp", provider.interoperability)

    def test_google_vertex_exposes_a2a(self):
        self.assertIn("a2a-1.0", get_provider("google-vertex").interoperability)

    def test_aws_exposes_mcp_and_a2a_gateway_paths(self):
        provider = get_provider("aws-bedrock")
        self.assertIn("mcp", provider.interoperability)
        self.assertIn("a2a-1.0", provider.interoperability)

    def test_vercel_exposes_openresponses(self):
        self.assertIn("openresponses", get_provider("vercel-ai-gateway").interoperability)


if __name__ == "__main__":
    unittest.main()
