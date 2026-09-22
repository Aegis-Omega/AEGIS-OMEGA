# Native provider fanout team V1

## Assembly, not another provider implementation

Parent: PR #598, `8b870bfd4d9517a80fe11f67644e91f90291ddc8`.
Imported fanout: PR #597, `7854d157525428ba206ed4fcdc0df6561a77c1fc`.

During integration, #598 advanced from `44c0df8669939fbbf98b5a39abdf9a9aa3eb89d7`
to the parent above. The complete GitHub compare reports only the addition of
`.github/workflows/provider-native-runtime-replay.yml`; every tested runtime
source remains unchanged. This candidate preserves that workflow unchanged.
It is explicitly scoped to PR #598, so it does not attest the new child PR.

The four #597 files are reused byte-for-byte. Existing #598 SDK runtime,
OpenAI/Anthropic/Google adapters, provider selection, registry and single-provider
team remain unchanged. No PR merge, SDK installation or deployment is performed.

`createProviderNativeFanoutTeamV1` connects:

```
existing fresh provider evidence and registry
  -> existing bounded fanout / preflight quorum
  -> existing per-provider native adapter
  -> existing concrete native SDK-runtime source
  -> host invocation authorizer
  -> lazy SDK import and native method
  -> existing native receipt creation and full-body validation
  -> required external verifier
  -> provider-labelled provenance bundle
```

The production source paths use `Agent` + `Runner.run`, `query`, and `LlmAgent` +
`InMemoryRunner.runAsync`, respectively. The new composition does not substitute
fake adapters, a new provider selector or an accept-all production verifier.
The SDK packages themselves are not installed or verified by this change.

## Host inputs and commitments

Supply `runtime` using `ProviderNativeSdkRuntimeOptionsV1`, a real `verifier`
using `FanoutVerifierV1`, and an `authorization_policy_hash`. There is no default
approval callback, policy hash, verifier or model. Host policy hashes are
commitments supplied by the host, not signatures or newly granted authority.
Models are configuration labels, not provider-attested model identity.

Models and the explicit existing runtime limits are captured at construction:
`maxTurns=2`, `maxOutputTokens=2048`, `maxEvents=64`, `maxTaskChars=64000` unless
explicitly configured otherwise. The existing SDK-runtime validator checks them.
The host authorization policy hash and complete runtime configuration are encoded
inside the original task before the existing fanout request commitment is made.
Consequently, a different model, limit or policy cannot reuse that task commitment.
The fanout's 16384-byte task ceiling includes this configuration envelope.

There is exactly one fanout instance per team. Its batch-ID replay guard,
256-batch lifetime limit, fixed verification quorum, maximum three providers and
maximum three concurrent lanes survive between `execute()` calls. Bounds are
per instance, not cluster-wide or monetary caps. A native invocation can contain
multiple model turns within its configured limit.

## Timeout and late-admission behavior

An aborted lane is checked before and after host authorization and module loading.
If authorization or loading finishes after timeout, no new native provider call
starts. Neither the authorizer nor module-loader promise is prematurely detached
from the outstanding-work accounting.

An already-started #598 SDK call may not cooperate with cancellation. The existing
fanout therefore retains its slot until settlement, blocks overlapping batches,
never sets `cancellation_confirmed=true`, and ignores late results when constructing
an already-issued receipt. This change does not claim remote cancellation or a
process sandbox. Trusted module loaders, authorizers and verifiers remain trusted
local code. No credentials or live user task content are added to this repository.

## Structural replay

`certifyProviderNativeFanoutTeamV1(originalInput, result, expectedConfiguration)`
reconstructs the bound task, checks the configuration shape and delegates to the
existing independent fanout certifier. Supply configuration from an independently
trusted source when verifying externally received results. Replay does not call
SDKs, authorizers or verifiers, authenticate provider signatures, or establish
scientific consensus or the correctness of the verifier policy.

## Verification

The 27 new shared contract cases run the actual selection, native adapters,
SDK-runtime source, fanout, native receipt validation and independent certifier.
Only SDK module boundaries are doubled. Fresh availability evidence and the
output verifier are explicitly synthetic test fixtures, not live availability.
The shared cases are registered in the ordinary Vitest integration suite.

Observed locally on the explicit source slice:

- RED before connection: 24 failures out of 27 cases; three negative cases passed.
- GREEN after connection: 27/27 new cases passed.
- Inherited fanout regression: 31/31 cases passed.
- Combined: 58/58 passed, zero failed/skipped/cancelled/todo.
- Temporarily deleting the abort guards made both late-admission falsifiers fail;
  restoring the original code restored the 58-test GREEN result.
- TypeScript 5.8.3 focused strict check: exit 0, including
  `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`, and unused checks.

The full runtime/adapter files were Git-blob verified against #598. Common hash
and registry dependencies are the previously verified #597 source slice, unchanged
between their common parent and #598. `provider-mesh.ts` includes original runtime
lines 1..514; core/sovereignty types are explicitly recorded declaration slices.
This is not a full Git checkout or full-project typecheck.

The actual project `npm test` attempt exited 127 (`vitest: not found`). An npm
registry probe failed with `EAI_AGAIN`. No lockfile was invented. Installed-SDK
compatibility, full Vitest/TSC/build/Gate8 and live SDK execution remain unverified.

Full-checkout verification commands after genuine dependency installation:

```
cd sovereign-omega-v2
npm ci
npm test -- test/integration/provider-native-fanout-team.test.ts test/unit/provider-native-fanout.test.ts
npm run typecheck
npm run build
```

## Unchanged authority boundary

```
authority_effect = NONE
durable_apply_performed = false
consensus_claim = NONE
write_authority = NOT_GRANTED
merge_authority = NOT_GRANTED
deploy_authority = NOT_GRANTED
financial_authority = NOT_GRANTED
LIVE_NATIVE_PROVIDER_EXECUTION = NOT_PERFORMED
```
