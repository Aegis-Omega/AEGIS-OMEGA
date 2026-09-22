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

The original 41 runtime tests execute the actual transpiled runtime with SDK doubles.
The original 9 team tests execute the actual team factory with explicit conductor,
native-adapter and runtime boundary doubles. Those 50 tests do not establish the
correctness of those substituted boundaries, actual SDK compatibility or a
successful provider call. They are executed with Node's test runner; a successful Vitest run is a separate obligation.

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

## Actual AEGIS chain and registry-integrity extension

The combined command above now executes **90 tests**: the original 41 + 9,
17 registry-integrity regressions, and 23 real-control-plane integration tests.
`load-repository-ts.mjs` transpiles the real relative source dependency closure
without replacing AEGIS modules. The chain suite executes the team, conductor,
registry, mesh, three native adapters, runtime, canonicalizer and hashing code.
Only the external provider SDKs are test doubles in that suite.

The registry checks now compare the complete supplied registry with the derived
canonical registry, not only its copied root. Identity, transport, capabilities,
authority fields, duplicate/unknown agents and caller mutation during awaits
are covered. Valid subset registries and existing valid receipt roots are
preserved. This change does not grant any invocation or mutation permission.

Real-chain tests verify inner native and outer conductor receipt bindings for
all three providers; stale/future/incomplete evidence and forged registries
stop before SDK loading. Three concurrent callers also preserve independent
tasks and receipt chains. This is a concurrency test of the existing execute
interface, not a new fan-out scheduler or a live provider experiment.

The #598 dedicated workflow runs all four Node suites with exact per-suite
counts (41, 9, 17, 23), alongside its unchanged focused Vitest obligations.
Local Node success does not establish hosted execution or installed-SDK
compatibility. No SDK package or lockfile is changed by this extension.
