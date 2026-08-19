# AEGIS-Ω Frontier Provider Mesh

This package is the provider-neutral execution seam for SOL. It exists to make frontier models, agent runtimes, MCP servers, and A2A agents interchangeable **without moving authority into any provider runtime**.

## Constitutional boundary

The only valid direction of authority is:

```text
operator / service intent
        |
        v
Automaton-3 admission
        |
        +--> proof-carrying work order (D2/D3 or any cost-incurring inference)
        +--> expected parent state
        +--> idempotency key
        +--> budget + token ceilings
        +--> evidence references
        +--> explicit operator approval for D3
        |
        v
governed provider router
        |
        +--> native provider transport
        +--> remote MCP
        +--> A2A 1.0 task
        |
        v
provider evidence (grants_authority = false)
        |
        v
AEGIS receipt / replay / canonical state gate
```

A provider success response proves only that the named provider operation returned the recorded result. It never grants AEGIS authority and never proves the semantic truth of model output.

## Implemented surfaces

| Provider/runtime | Primary seam | Interop seam | Credential model |
|---|---|---|---|
| OpenAI | Responses / Realtime / Agents SDK | MCP | server-side opaque reference |
| Anthropic | Messages API | MCP | server-side opaque reference |
| Google Vertex / Gemini | Vertex / ADK managed invoker | A2A 1.0 + MCP | workload identity / opaque reference |
| Microsoft Foundry | Foundry managed invoker | MCP | managed identity / opaque reference |
| AWS Bedrock / AgentCore | Bedrock managed invoker | MCP + A2A 1.0 | IAM / opaque reference |
| Vercel AI Gateway | OpenAI-compatible / OpenResponses | MCP | server-side opaque reference |
| xAI | OpenAI-compatible | OpenAI-compatible | server-side opaque reference |
| Mistral | OpenAI-compatible | OpenAI-compatible | server-side opaque reference |
| DeepSeek | OpenAI-compatible | OpenAI/Anthropic-compatible | server-side opaque reference |
| Qwen / DashScope | OpenAI-compatible | OpenAI-compatible | server-side opaque reference |
| NVIDIA NIM | OpenAI-compatible / NIM | OpenAI-compatible | server-side opaque reference |
| Hugging Face | Inference Providers | OpenAI-compatible | server-side opaque reference |

The registry describes capabilities; production endpoint configuration remains environment-specific. No credential value is committed here.

## Modules

- `work_order.py` — deterministic proof-carrying authorization envelope for consequential/cost work.
- `stream_lease.py` — execution-owner/generation/sequence fencing for SSE streams.
- `providers.py` — immutable frontier provider/protocol/capability registry.
- `router.py` — default-deny provider routing, payload-digest binding, idempotency, work-order enforcement, non-authoritative evidence normalization.
- `http_transport.py` — credential-isolated OpenAI Responses, Anthropic Messages, and configured OpenAI-compatible HTTP transports.
- `managed_transport.py` — SDK/identity seam for Vertex, Microsoft Foundry, and AWS Bedrock/AgentCore.
- `mcp.py` — remote MCP server contract with explicit tool allowlists and approval policy.
- `a2a.py` — A2A 1.0 endpoint/task envelope bound to the current stream owner/generation.

## Copenhagen recovery

The interrupted Work session had already narrowed cognitive-pipeline semantics but stopped before the execution guards. The remote repository still contained the old keyword-driven `agents/cognitive_pipeline.py`, so this branch adds `agents/cognitive_pipeline_auditbound.py` as the recovered audit-bound implementation:

- T0/T1 wording without bound evidence is demoted to T3/unverified;
- offline mode emits no synthetic research result;
- KAN hash-chain scope is explicitly `LOCAL_SCORING_LOG_INTEGRITY_ONLY`;
- hash integrity is not a truth proof.

This branch then completes the two items that were still pending when Work credits stopped: fenced SSE ownership and mandatory proof-carrying work orders before cost-incurring execution.

## Non-goals in this branch

This branch does **not** provision credentials, create cloud resources, change IAM/OAuth/DNS, spend provider credits, deploy production services, merge `main`, or declare any provider integration production-admitted. Those require separate exact-environment admission and receipts.

## Verification

```bash
python -m pip install jsonschema==4.23.0
python -m unittest agents.tests.test_cognitive_evidence_binding -v
python -m unittest discover -s platform/sol/tests -p 'test_frontier_*.py' -v
python -m unittest agents.tests.test_lut_kan_parity -v
```

The dedicated GitHub Actions workflow for this branch runs the same audit-bound tests and validates the JSON contracts without invoking any provider.
