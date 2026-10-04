# Sovereign Provider Mesh V1

Status: DRAFT / evidence-only architecture  
Authority effect: `NONE`

## Purpose

AEGIS must not confuse a provider being known, configured, enrolled in a program, or present in a billing account with that provider being available for a specific execution.

Provider Mesh V1 separates:

1. **declared provider capability** — what a provider class can potentially supply;
2. **observed provider availability** — what a terminal durable execution receipt proves was actually available;
3. **provider selection** — deterministic routing among only evidence-qualified providers;
4. **execution authority** — still decided separately by the existing sovereignty / Automaton-3 authority path.

A successful provider selection never grants repository, cloud, billing, model, data-movement, deployment, or mutation authority.

## Two planes

### Execution plane

Capability classes:

- `DURABLE_RUNNER`
- `CONTAINER_RUNTIME`
- `GPU_COMPUTE`
- `REPOSITORY_WORKFLOW`

### Intelligence plane

Capability classes:

- `MODEL_INFERENCE`
- `AGENT_EXECUTION`
- `REPOSITORY_AGENT`

A provider may participate in either or both planes.

## Declared catalog

The V1 catalog contains generic descriptors for:

- Anthropic
- GitHub Actions
- Google Cloud
- Nebius AI Cloud
- OpenAI

These descriptors are product/service capability declarations only.

They do **not** assert:

- that any operator account exists;
- that credits or promotional balances exist;
- that quotas are sufficient;
- that credentials are configured;
- that an endpoint is reachable;
- that a program application was accepted;
- that confidential or regulated data may be sent to that provider;
- that the provider may exercise any AEGIS authority.

Account-specific evidence remains outside the public repository.

## Observation rule

Only a terminal `DurableExecutionRecordV1` can mint a provider observation.

`SUCCEEDED` produces:

`OBSERVED_AVAILABLE`

A terminal failed, cancelled, or expired execution produces:

`OBSERVED_UNAVAILABLE`

An in-flight execution cannot mint an availability observation.

A terminal execution without a terminal receipt hash cannot mint an observation.

The terminal receipt hash becomes the observation evidence hash.

## Selection rule

A provider is eligible only when all of the following hold:

1. it is declared in the provider catalog;
2. it is allowed by the request, when an allow-list is supplied;
3. it has a fresh `OBSERVED_AVAILABLE` observation;
4. every requested capability appears in that observation;
5. the observation generation is not in the future;
6. the observation is within the request's maximum evidence age.

Provider preference is applied only after these evidence gates.

Program membership, account configuration, billing state, or static catalog membership cannot bypass the gates.

## Determinism

Provider descriptors and observations are normalized into deterministic order before the provider-mesh snapshot root is derived.

Routing uses:

1. explicit preferred-provider order, when supplied;
2. provider ID lexical order as the deterministic tie-breaker.

Input ordering must not change the snapshot root or routing result.

## Tamper boundary

Selection re-derives the provider-mesh snapshot from the supplied descriptors and observations.

A supplied `snapshot_root` that differs from the derived root is rejected before routing.

## Durable execution binding

A successful selection receipt can be bound to an existing `DurableExecutionRecordV1` by producing a new immutable record copy with:

- selected `provider`;
- concrete `executor_id`;
- provider-selection receipt root.

The source durable record is not mutated.

A denied selection receipt cannot be bound.

This binding remains:

`authority_effect = NONE`

## Relationship to Automaton-3

Provider Mesh answers:

> Which observed substrate can satisfy the requested execution capability?

Automaton-3 separately answers:

> Is this actor, tool, workspace, source state, approval, authority domain, and requested action admitted?

Provider availability is therefore evidence for routing, never evidence of authority.

## V1 non-claims

Provider Mesh V1 does not:

- provision cloud resources;
- create or rotate provider credentials;
- redeem credits or promotions;
- move data to an external provider;
- invoke a paid model;
- merge or deploy repository changes;
- certify provider uptime;
- guarantee execution success;
- infer availability from email, account membership, or billing configuration;
- replace the existing capability registry, writer lease, approval, receipt, or Automaton-3 authority boundaries.

## Next adapters

The V1 core deliberately leaves provider-specific adapters outside the authority-neutral selector.

Provider adapters may later translate successful terminal receipts from, for example:

- GitHub Actions;
- Google Cloud runtimes;
- Nebius runtimes;
- OpenAI agent/model execution;
- Anthropic agent/model execution;

into the same `ProviderObservationV1` contract.

Each adapter must preserve the rule that external provider evidence cannot self-grant AEGIS authority.
