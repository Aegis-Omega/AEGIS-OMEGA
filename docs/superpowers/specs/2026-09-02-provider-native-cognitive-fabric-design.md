# Provider-Native Cognitive Fabric v1

Status: RATIFIED DESIGN / IMPLEMENTATION IN PROGRESS

## Goal

Make every external model provider operate at its deepest provider-native reasoning configuration appropriate to the task while preserving AEGIS provider neutrality, replayability, exact provenance, capability boundaries, and the invariant that model intelligence never mints authority.

## Core invariant

`provider capability -> information amplification`, never `provider capability -> authority amplification`.

All model outputs remain candidate evidence until the existing AEGIS verification/admission spine promotes them.

## Architecture

`sovereign-omega-v2/src/agents/coordination/provider-cognition.ts` maps provider + work class into a deterministic `ProviderCognitiveProfile`. The profile records effective model, provider-native reasoning controls, tool policy, state policy, and the only authority available to raw output: `NONE`.

The first version supports OpenAI, Anthropic, DashScope/Qwen, Gemini, and local providers. Model slugs are refreshable capability defaults rather than constitutional identities. The exact selected model and reasoning configuration are bound into execution provenance.

Current quality-first defaults, verified against provider documentation on 2026-09-02:

- OpenAI: `gpt-5.6-sol`; frontier/formal work uses Responses API with `reasoning.effort=max` and pro mode.
- Anthropic: `claude-opus-5`; frontier/formal work uses adaptive thinking with `output_config.effort=max`; implementation uses `xhigh`.
- Gemini: `gemini-3.1-pro-preview`; non-routine work uses Interactions API with `thinking_level=high`.
- DashScope/Qwen: `qwen3.8-max`; non-routine work uses Responses API with `reasoning.effort=xhigh` (maximum-intensity Qwen3.8 reasoning).
- Local: strongest configured local reasoner; non-routine work uses deep mode.

## Work classes

- `frontier-research`: hardest mathematical/scientific/architectural work; maximum quality.
- `formal-review`: theorem/proof/security/adversarial verification; maximum quality and tool-constrained.
- `implementation`: code generation/refactoring/debugging; extended deep reasoning with workspace tools behind AEGIS capability policy.
- `routine`: lower-cost/latency work; still provider-native, with explicit lower reasoning controls where supported.

## Provider-native execution contracts

Pure request builders make provider depth mechanically inspectable before any network call:

- `openai-responses.ts`: OpenAI Responses API, `store=false`, encrypted reasoning continuity, exact reasoning effort/mode, optional privacy-preserving `safety_identifier`.
- `anthropic-messages.ts`: Anthropic Messages API, adaptive thinking, hidden/omitted thinking display, explicit effort and work-class output cap.
- `gemini-interactions.ts`: Gemini Interactions API, `store=false`, explicit thinking level and no thought-summary disclosure.
- `qwen-responses.ts`: Alibaba Model Studio Responses API, `store=false`, explicit Qwen reasoning effort.

Every builder receives only an already-authorized tool list. Provider-native tool availability does not create AEGIS capability authority.

## Authority

Every profile has `raw_output_authority = "NONE"`. Provider responses, hidden reasoning, traces, hosted tool outputs, sandbox outputs, consensus, or agreement between providers cannot directly become T0/T1/T2 admission evidence. AEGIS receipts, independent verification, and existing admission policy remain load-bearing.

## OpenAI execution boundary

The existing product-chat compatibility endpoint may remain, but AEGIS cognitive execution targets the Responses API rather than legacy Chat Completions. OpenAI request provenance includes the effective model, reasoning effort/mode, state/storage policy, allowed tool classes, response identifier when present, and a privacy-preserving `safety_identifier` when an end-user identity is relevant.

For zero-retention/stateless operation, adapters never assume server-side conversation persistence. Returned state/reasoning items may be replayed only under configured retention policy.

## Tools and sandbox

Provider-native tools are subordinate capabilities. Read-only tools may be granted by a task capability manifest. Any write, execute, deploy, external-message, payment, merge, credential, hardware, or physical-device capability remains separately gated by AEGIS DecisionReceipt -> ExecutionReceipt -> EffectObservation -> EffectReceipt semantics.

Quantum simulation is diagnostic. Physical quantum hardware execution is a distinct capability and requires explicit operator/admission authorization plus hardware-bound observation evidence.

## Provenance

`ProviderExecutionReceiptV1` binds provider, exact model, work class, reasoning configuration, storage/tool policy, task digest, output digest, tool-policy digest and `authority_class = "NONE"`. Changing any bound execution property changes receipt identity.

## Non-goals

- Replacing AEGIS governance with OpenAI Agents SDK, Anthropic tools, Gemini agents, Alibaba Model Studio, or any provider framework.
- Hard-coding one provider as permanent coordinator or authority source.
- Treating stronger reasoning, multi-agent agreement, hidden chain-of-thought, or quantum diagnostics as proof.
- Claiming physical quantum teleportation. Physical teleportation remains `NOT_ESTABLISHED` until hardware-bound evidence exists.

## Acceptance criteria

1. A deterministic provider-profile selector covers all supported providers/work classes.
2. Frontier/formal work selects the deepest supported provider-native reasoning controls.
3. Routine work can choose a lower-cost profile without weakening provenance.
4. Every profile enforces raw output authority `NONE`.
5. Pure request builders exist for OpenAI, Anthropic, Gemini and Qwen and reject mismatched provider profiles.
6. Provider request builders default to stateless execution where the provider API supports it.
7. Tests fail if a provider profile can mint authority or if a frontier provider is downgraded below its configured deep-reasoning mode.
8. Existing provider-neutral quorum/admission/effect-verification semantics remain unchanged in this slice.
