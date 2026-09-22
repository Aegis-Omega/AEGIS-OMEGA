# Provider-native fan-out/fan-in V1

Parent: PR #595, source commit e985606bec0087b086a750bf05089beda0d4af96.

## Scope

Adds bounded parallel orchestration over the existing native-agent selection
contract and the return shapes from #589 (OpenAI), #591 (Anthropic), and #592
(Google ADK). It does not install those SDKs, launch providers, merge their
branches, deploy a service, or grant credentials, tool access or spending rights.
No provider calls are made by the test fixtures.

`createProviderNativeFanoutV1({ adapters, verifier })` accepts explicit provider
lanes. Each lane binds its provider_id to the existing adapter's execute method.
Native selection uses #588, not an LLM-authored routing decision. There is no
accept-all production verifier; verifier_id, policy_hash and verify are required.

## Bounds and receipts

At most three distinct supported providers (openai, anthropic, google-cloud)
per batch, at most three parallel lanes, one invocation per selected lane, and
no retries. min_verified is fixed before dispatch. If availability cannot meet
it, the batch dispatches nothing. Tasks are limited to 16,384 UTF-8 bytes and
native output to 65,536 UTF-8 bytes. Each deadline is 1..30,000 milliseconds.
There is one active batch per service instance and a 256-ID lifetime admission
cap. These are per-instance call/data bounds, NOT monetary or distributed quotas.

The batch ID and entire request commitment are included in each native task.
Native receipts are independently recomputed using the existing provider-specific
domains. Provider, agent, task, selection, output, model label, native ID and all
authority fields must match. Unexpected native fields are rejected. The complete
supplied native registry body is checked, not merely its stored root.

Independent verifier evidence binds the accepted native receipt to the batch
request and policy. Only passing lanes count toward the unchanged quorum.
The synthesis is a deterministic, provider-labelled JSON evidence bundle; it
preserves disagreement. It is not an additional model call, a truth vote, or
scientific consensus. Consensus claim and authority effect remain NONE;
durable_apply_performed is false.

## Timeout semantics

A timeout requests AbortSignal cancellation but records cancellation_confirmed
as false. A non-cooperative native runner may remain alive. Its slot is not
reused, no retry/fallback is launched, late completion cannot modify the returned
receipt, and another batch is refused until outstanding work actually settles.
This is not OS process termination or an in-process security sandbox.

## Verification

The shared cases in test/contracts/provider-native-fanout.cases.ts are registered
by test/unit/provider-native-fanout.test.ts into the existing Vitest suite.

Run from sovereign-omega-v2 after the existing lockfile dependencies are present:

    npm test -- test/unit/provider-native-fanout.test.ts
    npm test
    npm run typecheck
    npm run build

During construction, the same 31 assertions ran with node:test against a
connector-sourced runtime slice. Node v22.16.0: 31 passed, 0 failed. Focused strict
TypeScript 5.8.3 checking passed, including noUncheckedIndexedAccess and
exactOptionalPropertyTypes. The source slice contains full blob-verified
canonicalize.ts, hashing.ts and provider-native-agents.ts, provider-mesh.ts lines
1..514, and the required original branded/contract type declarations. It is not
a complete repository checkout. Local source-slice checks are not a Vitest,
full-repository TSC, build, hosted exact-head, or Gate8 execution receipt.

certifyProviderNativeFanoutV1(input, result) independently reconstructs structural
receipt bindings, leaf order, quorum accounting and synthesis. It does not
authenticate provider signatures or rerun/trust-proof the verifier algorithm.
Fresh provider availability and a permitted native runtime must still be
established outside the fixture lane. No live execution is claimed.
