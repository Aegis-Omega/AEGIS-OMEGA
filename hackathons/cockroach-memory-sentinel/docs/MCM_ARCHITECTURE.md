# MCM — Mycorrhizal Collective Metacognition

## Status

Hackathon-specific architecture slice. Bio-inspired systems metaphor only.

This document does **not** claim that fungal or forest networks possess metacognition. The biological analogy is used narrowly to motivate sparse, distributed signaling and resource-aware routing.

## Definition

> A sparse, distributed metacognitive substrate that propagates evidence, uncertainty, contradiction, resource pressure, and verification demand across heterogeneous agents without itself granting authority.

## State model

For node `i`, MCM maintains a sparse meta-state:

```text
M_t = { C_i, E_i, D_ij, L_i, R_i, A_i }
```

- `C_i` — confidence/calibration
- `E_i` — evidence state and freshness
- `D_ij` — disagreement/contradiction relations
- `L_i` — load/resource pressure
- `R_i` — reliability/history
- `A_i` — observed authority envelope only; never permission to expand it

## Constitutional boundary

MCM output is permanently bounded to:

```text
MCM observation
  -> OBSERVATION_ONLY / T2
  -> VCM/evidence candidate
  -> Authority Control Plane
  -> ADMITTED | DENIED | REVIEW_REQUIRED
```

Forbidden transition:

```text
MCM sensed risk
  -X-> direct authority mutation
```

Every MCM observation emitted by `src/mcm.mjs` hard-codes:

- `authorityEffect = OBSERVATION_ONLY`
- `observationTier = T2`
- `authorityWeight = 0`
- `mayGroundStateTransition = false`
- `proposedAuthorityEnvelope = null`

Resource pressure, low confidence, stale evidence, and contradiction may alter **routing priority** or **verification demand** only.

## CockroachDB memory role

CockroachDB is intended to be the persistent system of record for:

1. current sparse node meta-state;
2. structured evidence memories;
3. semantic evidence vectors;
4. immutable-style action receipt records and replay anchors.

The transactional state and semantic evidence vectors remain in one consistency domain. The vector path is used for candidate retrieval; retrieved material remains evidence and cannot grant authority.

## Memory-to-action gate

Before a consequential action, `evaluateMemoryAuthority()` compares the current request against the admitted memory tuple:

```text
(state_digest, policy_digest, authority_epoch, action_digest)
```

It fails closed on:

- stale state;
- stale policy;
- authority epoch mismatch;
- replay of an already receipted action;
- missing memory binding.

A valid semantic match or a highly confident MCM observation cannot override these checks.

## Relationship to pre-existing AEGIS work

AEGIS Omega predates this hackathon and contains separate metacognitive, replay, receipt, and authority-control experiments. Those are disclosed as pre-existing work.

The new hackathon slice is the specific CockroachDB/AWS-backed persistent-memory application, the MCM sparse collective layer, its new tests/schema/demo, and the required sponsor-tool integrations built during the submission period.
