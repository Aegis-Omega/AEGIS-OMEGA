# Provider-Native Cognitive Fabric v1

Status: RATIFIED DESIGN

## Goal

Make every external model provider operate at its deepest provider-native reasoning configuration appropriate to the task while preserving AEGIS provider neutrality, replayability, exact provenance, capability boundaries, and the invariant that model intelligence never mints authority.

## Core invariant

`provider capability -> information amplification`, never `provider capability -> authority amplification`.

All model outputs remain candidate evidence until the existing AEGIS verification/admission spine promotes them.

## Architecture

Introduce a pure provider-cognition policy module in `sovereign-omega-v2/src/agents/coordination/provider-cognition.ts`. It maps a provider plus work class into a deterministic `ProviderCognitiveProfile`. The profile records provider-native reasoning controls, tool policy, state policy, and the maximum authority class that any raw model output may claim.

The first version supports OpenAI, Anthropic, DashScope/Qwen, Gemini, and local providers. Models are configuration defaults rather than constitutional identities: environment/runtime policy may override the model slug, but the exact selected model and reasoning configuration must be recorded in execution provenance.

OpenAI quality-first work defaults to the current flagship reasoning family through the Responses API with maximum reasoning effort; Anthropic uses adaptive thinking with high effort; Gemini uses high thinking level; Qwen/local profiles use their strongest configured reasoning mode without pretending to provide a vendor feature that is unavailable.

## Work classes

- `frontier-research`: hardest mathematical/scientific/architectural work; quality-first.
- `formal-review`: theorem/proof/security/adversarial verification; quality-first and tool-constrained.
- `implementation`: code generation/refactoring/debugging; deep reasoning with workspace tools behind AEGIS capability policy.
- `routine`: lower-cost/latency work; still provider-native but not forced to maximum compute.

## Authority

Every profile has `raw_output_authority = "NONE"`. Provider responses, hidden reasoning, traces, hosted tool outputs, sandbox outputs, consensus, or agreement between providers cannot directly become T0/T1/T2 admission evidence. AEGIS receipts, independent verification, and existing admission policy remain load-bearing.

## OpenAI execution boundary

The existing product-chat compatibility endpoint may remain, but AEGIS cognitive execution must target the Responses API rather than legacy Chat Completions. OpenAI request provenance must include the effective model, reasoning effort/mode, state/storage policy, allowed tool classes, response identifier when present, and a privacy-preserving `safety_identifier` when an end-user identity is relevant.

For zero-retention/stateless operation, the adapter must not assume server-side conversation persistence. Returned reasoning/state items may be replayed only according to the configured data-retention policy.

## Tools and sandbox

Provider-native tools are subordinate capabilities. Read-only tools may be granted by a task capability manifest. Any write, execute, deploy, external-message, payment, merge, credential, hardware, or physical-device capability remains separately gated by AEGIS DecisionReceipt -> ExecutionReceipt -> EffectObservation -> EffectReceipt semantics.

Quantum simulation is diagnostic. Physical quantum hardware execution is a distinct capability and requires explicit operator/admission authorization plus hardware-bound observation evidence.

## Provenance

A `ProviderExecutionReceiptV1` must be constructible from the chosen profile and observed execution metadata. At minimum it binds provider, exact model, work class, reasoning configuration, tool-policy digest/input, task digest, output digest, and `authority_class = "NONE"`.

## Non-goals

- Replacing AEGIS governance with OpenAI Agents SDK, Anthropic tools, Gemini agents, or any provider framework.
- Hard-coding one provider as permanent coordinator or authority source.
- Treating stronger reasoning, multi-agent agreement, or quantum diagnostics as proof.
- Claiming physical quantum teleportation. Physical teleportation remains `NOT_ESTABLISHED` until hardware-bound evidence exists.

## Acceptance criteria

1. A pure deterministic provider-profile selector exists and covers all supported providers/work classes.
2. Frontier/formal work selects the deepest configured provider-native reasoning controls.
3. Routine work can choose a lower-cost profile without weakening provenance.
4. Every profile enforces raw output authority `NONE`.
5. Tests fail if a provider profile can mint authority or if frontier OpenAI/Anthropic/Gemini profiles are downgraded below their configured deep-reasoning mode.
6. Existing provider-neutral swarm/admission code remains semantically unchanged in this slice.
