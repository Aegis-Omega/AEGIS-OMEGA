# SOL Cross-Platform Control Plane

This directory is the governed integration boundary for AEGIS-Ω provider interoperability.

## What is implemented in this slice

- architecture and trust-boundary specification;
- canonical provider execution request/result schemas;
- proof-carrying work-order and fenced SSE stream schemas;
- machine-readable platform registry;
- fail-closed oGemma/MYTHOS evidence adapter;
- audit-bound cognitive pipeline recovery (`T0/T1 wording != authority`, no fabricated offline research, scoring hash != truth proof);
- frontier provider registry for OpenAI, Anthropic, Google Vertex/Gemini, Microsoft Foundry, AWS Bedrock/AgentCore, Vercel AI Gateway, xAI, Mistral, DeepSeek, Qwen/DashScope, NVIDIA NIM, and Hugging Face;
- default-deny governed provider router with payload-digest binding, idempotency, budget/token envelopes, and non-authoritative evidence normalization;
- server-side HTTP transport seam for OpenAI Responses, Anthropic Messages, and configured OpenAI-compatible providers;
- managed SDK/identity transport seam for Google Vertex, Microsoft Foundry, and AWS Bedrock;
- governed remote MCP contract with explicit tool allowlists;
- A2A 1.0 task envelope bound to current execution/stream ownership;
- adversarial adapter and frontier guard tests;
- OpenAI agent-runtime contract;
- Cloudflare remote MCP deployment contract;
- iOS App Intents/operator contract;
- web operator-console contract;
- SharePoint publication policy.

## Constitutional invariant

```text
provider/model proposes or computes
        -> Automaton-3 authorizes
        -> provider executes only inside the admitted capability/budget envelope
        -> provider result is evidence, never authority
        -> AEGIS records receipts/replay/canonical-state transition
```

Any D2/D3 execution and any cost-incurring inference requires a proof-carrying work order. D3 additionally requires explicit operator approval. D4 is denied in this slice. SSE/A2A streaming is fenced by execution identity, owner, generation, token, and monotone sequence.

## What remains deliberately unconfigured

- production credentials and secrets;
- live OpenAI/Anthropic/Google/Microsoft/AWS/Vercel/xAI/Mistral/DeepSeek/Qwen/NVIDIA/Hugging Face endpoint provisioning;
- Cloudflare Worker deployment and DNS;
- OAuth applications;
- Dataverse tables or migrations;
- NVIDIA runtime/container provisioning;
- Hugging Face model/dataset publication;
- Wolfram API credentials;
- Figma production-file mutation;
- SharePoint organizational library creation;
- iOS target/project changes;
- public ChatGPT app submission;
- merge to `main`.

Those operations require exact environment identities, provider-specific scopes, and Automaton-3 admission of the resulting implementation candidates.

## Existing assets integrated by contract

The first concrete adapter is the existing `clients/gemma-holon` oGemma/MYTHOS material. The adapter binds gate, task, plan, prompt, model, and biological-state digests into deterministic T2 evidence and denies unknown gates or malformed state.

The existing `sovereign-omega-v2/mcp-server` remains the canonical local MCP implementation. `platform/sol/frontier/` adds the provider-neutral execution, MCP, A2A, proof-carrying work-order, and stream-fencing boundary around provider-specific runtimes rather than creating a second authority evaluator.

## Validation

Run locally:

```bash
python -m pip install jsonschema==4.23.0
python -m unittest agents.tests.test_cognitive_evidence_binding -v
python -m unittest discover -s platform/sol/tests -p 'test_*.py' -v
python -m unittest agents.tests.test_lut_kan_parity -v
```

The dedicated Frontier Provider Mesh workflow performs exact-branch contract/test validation without provider credentials or network calls.

## Next engineering slices

1. Funnel legacy direct Anthropic/OpenAI/provider call sites through the governed router and eliminate bypass paths.
2. Wire real server-side credential resolvers (workload identity / managed identity / IAM / secret manager references) per deployment environment.
3. Bind the existing remote MCP server and provider MCP clients to the proof-carrying work-order envelope.
4. Add A2A agent-card discovery and signed task/result receipts for Google/AWS/other A2A peers.
5. Reconcile the older provider-neutral inference-gateway PR into this authority model rather than maintaining a parallel gateway.
6. Add end-to-end replay packages and exact-candidate attestations for each provider adapter.
7. Only after those receipts exist: perform separately admitted live sandbox probes per provider, then production admission.
