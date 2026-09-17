# AEGIS Ω — Mycorrhizal 1BNA Evidence Sync Design

**Status:** APPROVED_DESIGN / IMPLEMENTATION_NOT_YET_EVIDENCE  
**Date:** 2026-09-17  
**Exact implementation parent:** `db311cfc900f594dc24aa5cc842586495a43ce61` (`#264`, `feat/frontier-provider-mesh-v1`)  
**Authority effect:** `NONE`

## Goal

Synchronize the source-bound 1BNA structural benchmark into the existing AEGIS Mycorrhizal Collective Metacognition (MCM) path as a deterministic, replayable, zero-authority evidence observation.

The synchronization must not reinterpret the 1BNA benchmark as biological mechanism, standard 3DNA truth, model authority, admission, or effect authorization.

## Existing constitutional boundary

Every load-bearing MCM output must carry exactly:

```ts
authorityEffect: 'OBSERVATION_ONLY'
observationTier: 'T2'
authorityWeight: 0
mayGroundStateTransition: false
```

Allowed direction:

```text
bound evidence digest
  -> MCM node observation
  -> deterministic collective state
  -> verification request / review signal
```

Forbidden direction:

```text
MCM -/-> authority grant
MCM -/-> provider/tool execution
MCM -/-> lease/fencing authority
MCM -/-> EffectReceipt
MCM -/-> canonical state mutation
```

## Repository reconciliation

The canonical implementation directory already exists at:

```text
sovereign-omega-v2/src/metacognition/
```

The current Sensorium observation contract is:

```text
sovereign-omega-v2/src/sensorium/sensorium-observation.ts
```

The current test root is singular `test/`, not the stale `tests/` path from the 2026-08-16 draft plan:

```text
sovereign-omega-v2/test/unit/
```

## Components

### 1. MCM contracts

Create `mycorrhizal-contracts.ts` with:

- `McmNodeObservationInputV1`
- `McmNodeObservationV1`
- `McmVerificationReason`
- `McmVerificationRequestV1`
- `createMcmNodeObservation(...)`

All SHA-256 digests are lowercase 64-hex. All BPS values are safe integers in `[0,10000]`. Evidence references are non-empty, unique, canonical-sorted. Observation hashes use the repository canonical `hashValue()` path.

### 2. Deterministic collective state

Create `mycorrhizal-state.ts` with an order-insensitive reducer over a bounded observation set.

The reducer must:

- reject empty sets;
- reject mixed parent-state roots;
- reject mixed topology digests;
- reject malformed/authority-bearing observations;
- reject conflicting duplicate `(nodeIdentityDigest, observationSequence)` entries;
- sort observations by `(nodeIdentityDigest, observationSequence, observationDigest)`;
- compute equal-weight integer floor means for all six BPS metrics;
- bind constitutional constants, parent root, topology digest, ordered observation digests, and aggregate metrics into `stateRoot` using `hashValue()`.

### 3. Verification routing

Create `mycorrhizal-routing.ts` implementing the frozen v1 thresholds:

```text
calibration < 7000          -> LOW_CALIBRATION
evidenceSupport < 7000      -> LOW_EVIDENCE_SUPPORT
evidenceFreshness < 7000    -> STALE_EVIDENCE
resourcePressure >= 8000    -> RESOURCE_PRESSURE
contradictionPressure >=6000-> CONTRADICTION_PRESSURE
verificationDemand >= 7000  -> EXPLICIT_VERIFICATION_DEMAND
```

Routing emits verification requests only. It must reject observations not represented by the supplied collective state.

### 4. 1BNA structural-evidence adapter

Create `mycorrhizal-1bna.ts` as a pure adapter over a caller-supplied 1BNA evidence binding.

The adapter accepts only digests/metadata, never raw PDB telemetry. Required evidence identities:

```text
PDB source SHA-256:
df42f1506792f191b957227b061360652adcf6f813eb69d9ec553067ea584670

Python V3 benchmark digest:
0d23a1449c4110c11fe99809df1fd9bb55216d8b14eee75cdcff81f21f794276

V4 cross-runtime receipt digest:
f8197fa4ee9d37fd81bd4f3d1d9391d8eff153aefc3d0ff5e0ecce2ade1d053a
```

The V5 residue-hotspot artifact may be referenced by digest when supplied, but no code path may infer biological mechanism from its contents.

The adapter constructs an `McmNodeObservationInputV1` with conservative, explicit model-defined BPS values. It must not derive calibration or truth from numerical agreement alone.

Default 1BNA observation profile for v1:

```text
calibrationBps          = 6500
evidenceSupportBps      = 9000
evidenceFreshnessBps    = 8000
resourcePressureBps     = 1000
contradictionPressureBps= 0
verificationDemandBps   = 7500
```

Rationale: source binding and cross-runtime reproduction support evidence integrity strongly, while standard 3DNA/Curves+ equivalence and biological mechanism remain unestablished. Therefore calibration remains below the generic 7000 threshold and explicit verification demand remains above threshold.

These values are `MODEL_DEFINED`, not empirically calibrated.

## Required 1BNA verification behavior

For the canonical 1BNA binding, MCM should emit verification demand for at least:

```text
LOW_CALIBRATION
EXPLICIT_VERIFICATION_DEMAND
```

It must not emit admission, effect, lease, provider invocation, or canonical-state transition objects.

If the source digest or any required benchmark digest drifts, the adapter fails closed before an MCM observation is created.

If a caller attempts to encode a stronger semantic claim such as `BIOLOGICAL_MECHANISM_ESTABLISHED`, `STANDARD_3DNA_VERIFIED`, or any authority-bearing field, the adapter rejects it.

## TDD falsifiers

RED tests must cover:

1. missing MCM modules;
2. malformed digest rejection;
3. out-of-range BPS rejection;
4. duplicate evidence rejection;
5. authority-override rejection;
6. empty/mixed collective state rejection;
7. order-insensitive state root;
8. conflicting node-sequence rejection;
9. deterministic verification thresholds;
10. routing-state binding rejection;
11. exact 1BNA digest acceptance;
12. 1BNA digest drift rejection;
13. forbidden stronger-claim rejection;
14. 1BNA observation remains `OBSERVATION_ONLY/T2/0/false`;
15. 1BNA synchronization produces verification demand but no admission/effect surface.

## Verification and evidence boundary

After implementation:

```text
MCM_CODE_PRESENT               = exact-head only
MCM_FOCUSED_TEST_PASS          = only from observed execution
MCM_TYPECHECK_PASS             = only from observed execution
MCM_GATE8_PASS                 = only from observed execution
MCM_EXACT_HEAD_CI_PASS         = only from exact-SHA hosted execution
MCM_EMPIRICAL_VALIDATION       = NOT_ESTABLISHED
MCM_AUTHORITY_INTEGRATION_PASS = NOT_ESTABLISHED unless separately tested
MCM_PRODUCTION_ADMISSION       = NOT_ESTABLISHED
1BNA_BIOLOGICAL_MECHANISM      = NOT_CLAIMED
1BNA_STANDARD_3DNA_EQUIVALENCE = NOT_CLAIMED
authority_effect               = NONE
```

No merge, release, production admission, or authority expansion is part of this design.