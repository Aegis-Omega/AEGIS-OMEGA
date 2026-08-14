from __future__ import annotations

from dataclasses import dataclass


class ProviderRegistryError(KeyError):
    pass


@dataclass(frozen=True)
class ProviderDescriptor:
    id: str
    role: str
    native_protocols: tuple[str, ...]
    interoperability: tuple[str, ...]
    auth_reference_schemes: tuple[str, ...]
    streaming_modes: tuple[str, ...]
    capabilities: tuple[str, ...]
    default_consequence_class: str = "D3"
    grants_authority: bool = False


def _provider(
    id: str,
    role: str,
    native_protocols: tuple[str, ...],
    interoperability: tuple[str, ...],
    streaming_modes: tuple[str, ...],
    capabilities: tuple[str, ...] = ("inference.run", "model.read"),
) -> ProviderDescriptor:
    return ProviderDescriptor(
        id=id,
        role=role,
        native_protocols=native_protocols,
        interoperability=interoperability,
        auth_reference_schemes=("secret://", "env://", "vault://", "keyref://", "oidc://", "identity://"),
        streaming_modes=streaming_modes,
        capabilities=capabilities,
    )


FRONTIER_PROVIDERS: tuple[ProviderDescriptor, ...] = (
    _provider(
        "openai",
        "frontier_agent_and_inference_runtime",
        ("responses-api", "realtime-api", "agents-sdk"),
        ("mcp", "function-tools"),
        ("sse", "websocket", "webrtc"),
        ("inference.run", "agent.run", "tool.call", "model.read"),
    ),
    _provider(
        "anthropic",
        "frontier_agent_and_inference_runtime",
        ("messages-api",),
        ("mcp",),
        ("sse",),
        ("inference.run", "agent.run", "tool.call", "model.read"),
    ),
    _provider(
        "google-vertex",
        "frontier_agent_and_inference_runtime",
        ("gemini-generate-content", "vertex-ai", "adk"),
        ("a2a-1.0", "mcp"),
        ("sse",),
        ("inference.run", "agent.run", "a2a.call", "tool.call", "model.read"),
    ),
    _provider(
        "microsoft-foundry",
        "enterprise_agent_and_inference_runtime",
        ("foundry-agent-service", "azure-openai-compatible"),
        ("mcp",),
        ("sse",),
        ("inference.run", "agent.run", "tool.call", "model.read"),
    ),
    _provider(
        "aws-bedrock",
        "enterprise_agent_and_inference_runtime",
        ("bedrock-converse", "agentcore-gateway"),
        ("mcp", "a2a-1.0"),
        ("sse",),
        ("inference.run", "agent.run", "a2a.call", "tool.call", "model.read"),
    ),
    _provider(
        "vercel-ai-gateway",
        "multi_provider_inference_gateway",
        ("openai-responses-compatible", "anthropic-messages-compatible"),
        ("openresponses", "mcp"),
        ("sse",),
        ("inference.run", "model.read"),
    ),
    _provider(
        "xai",
        "frontier_inference_runtime",
        ("openai-compatible",),
        ("openai-compatible",),
        ("sse",),
    ),
    _provider(
        "mistral",
        "frontier_inference_runtime",
        ("openai-compatible",),
        ("openai-compatible",),
        ("sse",),
    ),
    _provider(
        "deepseek",
        "frontier_inference_runtime",
        ("openai-compatible",),
        ("openai-compatible",),
        ("sse",),
    ),
    _provider(
        "qwen-dashscope",
        "frontier_inference_runtime",
        ("openai-compatible",),
        ("openai-compatible",),
        ("sse",),
    ),
    _provider(
        "nvidia-nim",
        "accelerated_inference_runtime",
        ("openai-compatible", "nim"),
        ("openai-compatible",),
        ("sse",),
        ("inference.run", "benchmark.run", "model.read"),
    ),
    _provider(
        "huggingface",
        "models_datasets_and_inference_runtime",
        ("inference-providers",),
        ("openai-compatible",),
        ("sse",),
        ("inference.run", "model.read", "dataset.read", "eval.run"),
    ),
)

_BY_ID = {provider.id: provider for provider in FRONTIER_PROVIDERS}
if len(_BY_ID) != len(FRONTIER_PROVIDERS):
    raise RuntimeError("duplicate frontier provider id")


def get_provider(provider_id: str) -> ProviderDescriptor:
    try:
        return _BY_ID[provider_id]
    except KeyError as exc:
        raise ProviderRegistryError(f"unknown frontier provider: {provider_id}") from exc
