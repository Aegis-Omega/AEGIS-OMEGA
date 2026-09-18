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
5. complete required gate/verifier set;
6. proof-carrying bridge bundles bound to the exact source-target-criterion relation;
7. exact-head registered verifier replay reproduces each carried receipt;
8. every replayed verifier verdict is PASS.

The executable result is either:

- `DENY`; or
- `ELIGIBLE_FOR_SEPARATE_TARGET_TRANSITION_ONLY`.

A PASS never mutates the target claim. It never grants repository, runtime,
clinical, biological, quantum, or production authority.

This implements the standing rule:

`admitted_authority <= weakest_verified_transition`.

If one required transition is missing, failed, malformed, stale, unregistered,
not replayable, or spliced, the cross-boundary result is denied.

## Raw receipts are not authority

The first V1 candidate accepted relation-bound, hash-valid `GateReceipt` objects
directly. Adversarial review rejected that surface because
`relation_gate_receipt(..., verdict=PASS, ...)` is a generic receipt constructor.

That would allow a caller-minted PASS object to satisfy a bridge criterion without
showing that the domain-specific verifier actually ran.

The corrected V1 therefore rejects raw `GateReceipt` objects with
`FAIL_RAW_OR_UNVERIFIED_GATE_BUNDLE`.

The evaluator accepts only `VerifiedBridgeGateV1` bundles. Each requirement pins
both a `gate_id` and a `verifier_id`. The bundle carries the exact relation,
evidence and receipt. Verification looks up the verifier in the exact-head
registry, re-executes it on the carried evidence, and requires semantic receipt
reproduction.

An unknown verifier id produces `FAIL_UNREGISTERED_VERIFIER`.

This deliberately follows the #324 principle that a raw hash-valid receipt is
not promotion authority by itself.

## Exact-head verifier registry

This first implementation registers only one verifier:

`SYNTHETIC_LITERAL_BOOL_BRIDGE_V1`.

It exists solely as a positive control proving that the gate is capable of an
eligible result when all proof-carrying obligations are present.

No QBP, clinical, formal-to-empirical, or finite-to-global scientific verifier is
registered by this lane. Therefore the real frozen cases remain DENY even if a
caller attempts to inject a raw PASS receipt.

Future bridge work must add its domain verifier implementation and change the
criterion epoch to pin that verifier identity.

## Reused substrate

No parallel receipt system is introduced. The implementation reuses the #324/#320
primitives:

- `RelationBindingV1`;
- `bind_relation`;
- `GateReceipt`;
- `relation_gate_receipt`;
- deterministic canonical SHA-256 material.

The bridge relation binds:

- source claim digest;
- target claim digest;
- bridge criterion digest.

A bundle for a different source, target, criterion, gate, or verifier is rejected.

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
their dedicated registered/replayable bridge verifiers:

1. CSTAR #522 machine-verified H3 normalization -> QBP-01 empirical optical phenotype;
2. EXP02 cross-species period-3 pipeline replication -> QBP-01 optical phenotype;
3. QBP-01 classical optical lane -> QBP-02 quantum witness;
4. QBP-02 higher-order witness -> quantum biological information channel;
5. PR #523 finite source calculus -> global Weil positivity;
6. PR #486 replay integrity -> clinical validity.

These are not statements that the target claims are false. They are statements
that source evidence does not carry target authority across an unverified boundary.

## Positive and negative controls

The regression suite includes a synthetic source/target pair with three changed
axes and two proof-carrying, replayable PASS bundles. That case becomes
`ELIGIBLE_FOR_SEPARATE_TARGET_TRANSITION_ONLY`.

Negative controls cover:

- raw caller-minted hash-valid PASS receipts;
- missing required proof bundle;
- source/target/criterion relation splicing;
- tampered receipt witness;
- no actual boundary change;
- invalid source status;
- unregistered real-domain verifiers;
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

## Corpus expansion: uploaded boundary evidence (2026-09-18)

The V1.1 coordinate `(domain_id, carrier_id, scope_id)` is sufficient for the newly
inspected corpus without adding a schema axis. Temporal currentness, trust/authentication,
jointness/topology, and execution freshness belong in criterion-pinned verifier obligations;
they must not be inferred from a coarse coordinate label.

New frozen boundary families:

- **classical null precursor -> full empirical bridge**: the QBP-01 public-null package
  deterministically replays a classical yeast precursor and explicitly keeps the
  GBA1/SPNS1 optical bridge, full QBP-01 bridge, and quantum claim NOT_ESTABLISHED.
- **encoding -> authentication -> activation**: AMIL's complete pinned-SDK integration
  verifies canonical bridge bytes/digests locally, while its own diagnostic records
  input authentication as NOT_ESTABLISHED and activation as NOT_IMPLEMENTED.
- **historical union -> current state**: the Nerve-ET source states that the historical
  union is a provenance layer and cannot decide current globalizability; epoch, time,
  namespace, modulus, policy, supersession and joint receipts must be rebuilt.
- **pairwise -> joint/global**: the cover-obstruction source distinguishes pairwise
  reconciliation from a genuine joint intersection and from existence of a global section.
- **prepared source -> kernel theorem**: the uploaded Abjad candidate is pinned but
  declares SOURCE_PREPARED_NOT_KERNEL_CHECKED; source text does not become formal authority.
- **sealed evaluator -> benchmark efficacy**: the ASB-1 package freezes 72 gold records
  (30 VALID, 30 INVALID, 12 UNRESOLVED) and scoring infrastructure, but contains no
  matched CONTROL/AEGIS arm run results; evaluator integrity is not efficacy evidence.
- **historical audit -> current conformance**: the 10 September JCS audit is a pinned
  snapshot finding and cannot establish the current implementation state without a fresh
  exact-source conformance transition.
- **architecture DAG -> action authority**: the Quantum overview explicitly labels bridge
  obligations and says the witness-to-authority edge is candidate-only, with no automatic ADMIT.

The uploaded corpus is bound by SHA-256 metadata only. Archive inspection in this
transition is read-only; unexecuted source bundles are explicitly marked as such.
The new cases are negative-control fixtures for authority transfer, not promotion receipts.

The existing EXP02 fixture was also rebound from an ungrounded placeholder digest to the
actual uploaded `verification_receipt.json` SHA-256
`cb9220d416d4ec28371fa0043f60d625ac82f681496011c12c4888c20e17c49c`.
Its target now uses the QBP public-null verification receipt that explicitly records the
GBA1/SPNS1 optical bridge as NOT_ESTABLISHED.

## Uploaded corpus expansion round 2 — 2026-09-18

The second uploaded bundle adds six non-redundant negative-control transitions while
leaving the V1.1 gate schema and verifier registry unchanged.

### New load-bearing boundaries

1. **1BNA coordinates -> GTG model parameterization.**
   The geometry benchmark is numerically bound to the supplied 1BNA coordinates,
   but labels helical quantities as coordinate proxies, leaves hydrogen-bond
   orientation unevaluated, and claims no biological mechanism. The GTG replay,
   independently, verifies population/coherence agreement for a 6-site model but
   explicitly excludes parameter regeneration and physical validation. A structure
   -> Hamiltonian/dephasing bridge therefore remains open.

2. **Numerical replay -> current source provenance.**
   The GTG replay is internally consistent to its stated tolerance, but its declared
   source commit `b0a840015f92f39ddae65beb7393bf2c91aa816e` still returns HTTP 422
   on a fresh connected GitHub commit read. Reproducible arrays cannot manufacture
   a currently addressable source commit.

3. **Package replay -> scientific admission.**
   `AEGIS_Claim_Validation_V3_package_check` covers its archive and passes packaged
   tests plus optimized replay, while its fresh receipt explicitly records
   `formal_kernel_executed=false`, `experimental_gate_evaluation_executed=false`,
   `repository_requests_executed=false`, admission not established, and
   `authority_effect=NONE`.

4. **Unrelated upstream build -> uploaded Lean theorem.**
   The supplied upstream build log ends with `Build completed successfully (8907 jobs)`
   and names `FormalConjectures.Wikipedia.Transcendental` as its final target.
   It does not bind the separately uploaded `AbjadFactorizationV1` or
   `AegisModuloRingV1` bytes into that build graph. Both files are lexically
   sorry-free and request `#print axioms`, but that is source evidence, not a
   kernel replay.

5. **Local source-slice replay -> deployed dispatch effect.**
   PR #342's independent package is internally coherent: outer SHA256SUMS 29/29,
   nested capsule manifest 33/33, candidate tests 40/40 under normal/-O/-OO,
   original-source negative control fails 27/40 as expected, and 5/5 mutations are
   detected. Its own receipt nevertheless states local source-slice scope,
   `live_dispatch=false`, `remote_writes=0`, and `authority_effect=NONE`.
   The live PR still points at the package source commit, but deployed effects remain
   a distinct transition.

6. **Cognitive admission -> runtime wiring.**
   The historical PR #423 package for `dcbd6a31...` verifies Automaton-2 and
   Trusted Cognitive Admission as ADMITTED. The same exact-candidate Integration
   Ledger reports `0 WIRED · 22 LINKED · 6 DORMANT · 8 ORPHAN` and says execution
   remains unverified. The current PR #423 head has since advanced to
   `2d6289a9522cfafe0788a6a9d949c46d05fbd99a`, so the uploaded package is retained
   only as historical exact-head evidence.

### Supporting evidence retained without a new boundary class

- The 1BNA residue hotspot map is structurally consistent with the geometry package
  for the two directly comparable columns: 24/24 pair-contact values and 24/24
  water-polar-contact counts match. Its diagnostic score remains a derived heuristic,
  not biological validation.
- The Coq census contains 36 rows: 33 marked closed under the global context, 3 not
  closed; 32 rows are tagged AUTHORITY_ELIGIBLE and 4 DIAGNOSTIC_ONLY. Census status
  does not discharge the already-frozen finite-to-global Weil/RH bridge.
- `AegisModuloRingV1` is retained as a separately hashed Lean source candidate; the
  existing source-to-kernel boundary class already covers its missing execution step.

No user-supplied executable from this round was run. Archive and checksum validation,
JSON/CSV comparison, and source inspection were read-only.

## Quantum / AegisQ / Self-Witness expansion — 2026-09-18

This expansion corrects an earlier omission: the quantum program is not represented by
one generic simulation boundary. The corpus contains distinct Self-Witness, QuanPhotonic/
QP-PD, AegisQ, and QuantumDNA surfaces with different evidence classes and independent
promotion obligations.

### Self-Witness-0

PR #373's actual qpp-cpu implementation bytes are preserved at the current live head
`7853f4e63029b24c987f9bdd2f58df8fcffa92d6`; the module blob remains
`815ddcd0a8f53926414ea400be2d428e53beab69`, identical to the execution-bound
head `6965e93bf892df556e86a07e12fddb540639125a`.

The real Self-Witness workflow at 6965 succeeded, including qpp-cpu CUDA-Q execution.
However:
- NVIDIA fp64 differential execution is NOT_RUN;
- physical QPU is OUT_OF_SCOPE_FOR_V1;
- physical-QPU promotion requires a shot-based V2 statistical contract;
- the current PR head has not received a fresh exact-head execution rebind.

Therefore qpp-cpu analytic execution is retained as SIMULATION evidence and cannot
promote either GPU differential closure or an EMPIRICAL physical-QPU witness.

### QP-PD / QuanPhotonic

PR #409 exact head `4626389c7866bc5faa2a21bb0f60fbd72329938a` has successful
`QP-PD V2 Biological Binding` evidence for software-level context binding,
anti-splicing, V2 receipt propagation, and schema/content-addressing behavior.

Its own bounded disposition keeps:
- empirical run NOT_PERFORMED;
- genuine CalibrationReceipt/raw detector payload still required;
- nonclassical biological photon statistics NOT_ESTABLISHED;
- Parkinson-specific UPE NOT_ESTABLISHED;
- biological predictive value and observability gain NOT_ESTABLISHED.

Thus software binding -> HBT/nonclassicality is a separate empirical bridge.

### AegisQ

PR #420 exact head `6987c08e843af03a644114413ea3da9331c460f2` has a successful
`AegisQ IFG Research Binding` run. Its own output is explicitly
`PASS_RESEARCH_ONLY` with `clinical_admissible=false`; numerical consistency does
not establish clinical accuracy, causality, predictive validity, or the proposed 0.1 ms bound.

The independent typed quantum DAG also leaves
`AQ_CALIBRATE -> AQ_PREDICTIVE_GAIN` OPEN and requires empirical holdout calibration,
-Q/classical-only ablations, and out-of-sample validation. The exact-head evidence brief
classifies the AegisQ network as PROPOSED ARCHITECTURE and states that architecture
diagram != deployed system and constraint satisfaction != predictive validity.

### QuantumDNA / GTG

The existing GTG replay remains a 6D numerical simulation result, not physical measurement
authority. This expansion adds the explicit missing bridge from a successful numerical
trajectory replay to a genuine corrected HBT nonclassicality witness.

New frozen cases:
1. QuantumDNA/GTG replay -> empirical HBT nonclassicality;
2. Self-Witness qpp-cpu -> NVIDIA fp64 differential;
3. Self-Witness analytic execution -> physical QPU statistical witness;
4. QP-PD V2 software binding -> biological nonclassicality;
5. AegisQ research-only IFG binding -> clinical/causal validity;
6. AegisQ architecture -> OOS predictive gain.

No new domain verifier is registered by this transition. All six real cases must remain
DENY until their criterion-pinned proof bundles exist.
