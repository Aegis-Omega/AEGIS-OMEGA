# Provider-native SDK runtime V1

Extends the assembled agent tree in PR #596 at
`65138ff74a610405e88950c8162115b2bd62e09c`.

`createProviderNativeAgentTeamV1` connects the existing provider mesh, registry,
conductor and three native adapters to these lazy-loaded execution paths:

- OpenAI: `@openai/agents` -> `Agent` + `Runner.run`.
- Anthropic: `@anthropic-ai/claude-agent-sdk` -> `query`.
- Google: `@google/adk` -> `LlmAgent` + `InMemoryRunner.runAsync`.

Construction performs no SDK import or provider call. Every native invocation
requires the host-owned `authorize(request)` callback to return exactly `true`.
Supply explicit models from trusted host configuration, not task input. An
invocation grant is not repository-write, merge, deployment or financial
authority for an agent. Cost approval and credentials remain host concerns.

The team preserves the existing fresh-evidence selector, requires both
`AGENT_EXECUTION` and `MODEL_INFERENCE`, and invokes only the selected provider.
The existing adapters and conductor bind their own selection/execution receipts.
Failed selection, authorization, SDK loading or terminal-output validation must
not be converted to a successful execution receipt.

No tools or handoffs are configured. OpenAI tracing and response storage are
disabled. Claude tools, ambient settings/MCP configuration and session
persistence are disabled in the query options; Google sessions are in-memory.
These are reviewed configuration choices, not proof of a process sandbox. Run
native SDKs in an isolated host without unrelated credentials or writable data.
Event/turn limits do not establish a wall-clock timeout or a monetary cost cap.
`maxOutputTokens` applies to OpenAI and Google, not Claude Agent SDK.

## Offline verification

With the repository's TypeScript development dependency installed:

```sh
cd sovereign-omega-v2
node --test test/native-runtime/*.test.mjs
npx --no-install tsc --noEmit --strict --target ES2022 --module ES2022 \
  --moduleResolution bundler --lib ES2022,DOM \
  src/sovereignty/provider-adapters/provider-native-sdk-runtime.ts
```

The 41 runtime tests execute the actual transpiled runtime with SDK doubles.
The 9 team tests execute the actual team factory with explicit conductor,
native-adapter and runtime boundary doubles. These 50 tests do not establish the
correctness of those substituted boundaries, actual SDK compatibility or a
successful provider call. They are separate from the default Vitest suite.

## Deliberately unclosed boundaries

No SDK dependency or lockfile is changed by this candidate. A host must admit and
install compatible, pinned SDK versions before using the default module loader.
Full repository typecheck/tests, installed-SDK integration, live provider calls
and exact-head hosted replay have not been performed by this transition.
The original PR #581 hosted-read replay residual remains separate and open.

```
write_authority = NOT_GRANTED
merge_authority = NOT_GRANTED
deploy_authority = NOT_GRANTED
financial_authority = NOT_GRANTED
authority_effect = NONE
live_execution = NOT_PERFORMED
```
