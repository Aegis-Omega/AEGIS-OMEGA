# Cross-Boundary Authority V1

Status: DRAFT VERIFIER-ONLY IMPLEMENTATION  
Parent: Cross-Domain Collision V1 (#324)  
Authority effect: NONE

## Purpose

Cross-Domain Collision V1 answers a structural question: can exact, provenance-bound
observations about one subject be replayed across independently identified domains
without confusing coincidence with mechanism?

Cross-Boundary Authority V1 answers a different question:

> When may evidence valid in one claim coordinate contribute to a stronger claim
> whose domain, evidence carrier, or scope is different?

A claim coordinate is the tuple:

`(domain_id, carrier_id, scope_id)`.

Changing any coordinate axis is an authority boundary.

## Core rule

A boundary crossing is denied unless all of the following are exact-bound:

1. source claim identity and evidence digest;
2. target claim identity and current target status;
3. source and target coordinates;
4. literal bridge criterion epoch;
5. complete required gate set;
6. PASS gate receipts bound to the exact source-target-criterion relation;
7. receipt integrity.

The executable result is either:

- `DENY`; or
- `ELIGIBLE_FOR_SEPARATE_TARGET_TRANSITION_ONLY`.

A PASS never mutates the target claim. It never grants repository, runtime,
clinical, biological, quantum, or production authority.

This implements the standing rule:

`admitted_authority <= weakest_verified_transition`.

If one required transition is missing, failed, malformed, stale, or spliced,
the cross-boundary result is denied.

## Relation binding

The lane reuses #324/#320 primitives instead of defining a parallel receipt system:

- `RelationBindingV1`;
- `GateReceipt`;
- `relation_gate_receipt`;
- deterministic SHA-256 material.

The bridge relation binds:

- source claim digest;
- target claim digest;
- bridge criterion digest.

A PASS receipt for a different source, target, or criterion is invalid even if
its gate id is otherwise expected.

## Boundary axes

### DOMAIN

Example: computational genomic-spectrum evidence -> QBP-01 biological optical lane.

A valid result about period-3 coding enrichment has no classical optical authority
without an explicit spectrum-to-optical bridge and empirical receipts.

### CARRIER

Example: QBP-01 classical optical observables -> QBP-02 quantum witness.

Classical intensity, spectrum, Stokes, or correlation measurements do not by
themselves establish antibunching or higher-order nonclassicality.

Example: PR #486 integrity/replay -> clinical validity.

Replay integrity can certify what bytes and annotations were bound. It does not
establish biological correctness or patient-level clinical validity.

### SCOPE

Example: PR #523 finite source calculus -> global Weil positivity.

A finite machine-checked identity does not promote to a global sign theorem without
the missing operator identity, finite-to-global control, and global sign transfer.

## QBP v0.4.1 example

The frozen fixture is derived from the supplied
`AEGIS_QBP_v0.4.1_CONTROL_PLANE_PACKAGE`.

Package replay performed during preparation of this lane:

- all 10 package-manifest member hashes matched;
- standalone control-plane files were byte-identical to the corresponding source-tar files;
- fresh source replay: `45 passed`;
- `compileall`: PASS;
- authority_effect: NONE.

One documentation drift was found:

- `REPLAY.md` says the expected suite contains 35 pytest cases;
- the control-plane receipt and fresh replay contain 45 passing cases.

Disposition: stale documentation only. The machine receipt remains the stronger
evidence. This drift is not transformed into a scientific failure and does not
promote any claim.

## Frozen fail-closed examples

The fixture asserts that all of the following remain DENY in the absence of
their dedicated bridge receipts:

1. CSTAR #522 machine-verified H3 normalization -> QBP-01 empirical optical phenotype;
2. EXP02 cross-species period-3 pipeline replication -> QBP-01 optical phenotype;
3. QBP-01 classical optical lane -> QBP-02 quantum witness;
4. QBP-02 higher-order witness -> quantum biological information channel;
5. PR #523 finite source calculus -> global Weil positivity;
6. PR #486 replay integrity -> clinical validity.

These are not statements that the target claims are false. They are statements
that source evidence does not carry target authority across an unverified boundary.

## QBP-specific correspondence

The QBP package already contains the same principle locally:

- `QBP-01` forbids quantum fields in its classical intake;
- `spectrum_to_quantum_bridge = NOT_ESTABLISHED`;
- QBP-02 says Q4 does not imply a quantum biological information channel;
- Q6 is necessary but not sufficient for that channel claim.

Cross-Boundary Authority V1 lifts that pattern into a reusable repository-level
gate without weakening the QBP-specific preregistrations.

## Positive control

The regression suite includes a synthetic source/target pair with three changed
axes and two relation-bound PASS receipts. That case becomes
`ELIGIBLE_FOR_SEPARATE_TARGET_TRANSITION_ONLY`.

Negative controls cover:

- missing required gate;
- source/target/criterion relation splicing;
- tampered receipt witness;
- no actual boundary change;
- invalid source status;
- all frozen QBP/repository examples.

## Explicit non-claims

This lane does not prove or establish:

- any QBP empirical result;
- any quantum biological information channel;
- clinical validity;
- global Weil positivity;
- RH;
- causation from cross-domain collision;
- repository admission;
- production authority.

It supplies only a fail-closed authority-transfer boundary.

## Governance

- verifier-only;
- stacked on exact #324 implementation;
- no merge or deployment intent;
- no external effects;
- authority_effect = NONE.
