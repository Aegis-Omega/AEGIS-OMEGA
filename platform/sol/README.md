# SOL Cross-Platform Control Plane

This directory is the governed integration boundary for AEGIS-Ω provider interoperability.

## What is implemented in this slice

- architecture and trust-boundary specification;
- canonical provider execution request/result schemas;
- machine-readable platform registry;
- fail-closed oGemma/MYTHOS evidence adapter;
- adversarial adapter tests;
- exact-scope CI validation;
- OpenAI agent-runtime contract;
- Cloudflare remote MCP deployment contract;
- iOS App Intents/operator contract;
- web operator-console contract;
- SharePoint publication policy.

## What remains deliberately unconfigured

- production credentials and secrets;
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

The existing `sovereign-omega-v2/mcp-server` remains the canonical local MCP implementation. A later implementation slice will expose a remote authenticated transport on Cloudflare without creating a second authority evaluator.

## Validation

Run locally:

```bash
python -m pip install jsonschema==4.23.0
python -m unittest discover -s platform/sol/tests -p 'test_*.py' -v
```

The `SOL Cross-Platform Integration` workflow validates JSON/schema syntax, executes the adapter test matrix, and rejects obvious committed credentials or mutable database files.

## Next engineering slices

1. Wire the adapter into the MYTHOS stage boundaries and replace the legacy unknown-gate approval path.
2. Add the OpenAI Agents SDK orchestrator against the existing governed MCP tools.
3. Implement the authenticated Cloudflare remote MCP transport.
4. Add standard `search`/`fetch` knowledge tools for GitHub, SharePoint, and Hugging Face.
5. Add Wolfram verification and NVIDIA evaluation worker adapters.
6. Generate three operator-console visual concepts, select one, and implement the React/MCP widget.
7. Add the SwiftUI operator client and three App Intents.
8. Publish reviewed runbooks into an organizational SharePoint library.
9. Add end-to-end evals, replay packages, and exact-candidate attestations.
