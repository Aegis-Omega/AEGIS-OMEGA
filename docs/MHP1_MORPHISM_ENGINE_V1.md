# AEGIS MHP-1 / Antropolimorphic Morphism Engine V1

Status: DRAFT / evidence-only / admission external.

## Core invariant

A semantic or mathematical transformation may preserve, omit, add, transport,
represent, globalize, or reinterpret knowledge, but the transformation does not
mint authority.

`MorphismReceipt.authority_class == NONE` is invariant. Canonical authority can
only arise from an independent AdmissionRecord issued by the existing admission
plane.

## Pipeline

`Payload -> trusted extraction -> ClaimSetReceipt -> HeritageVerifier -> HeritageReceipt -> HERITAGE proof-trace span`

Generalized:

`MorphismEnvelope -> kind-specific verifier -> MorphismVerificationRoot -> MorphismReceipt -> proof-trace evidence`

Canonical admission is deliberately outside this chain.

## Morphism kinds

- CARRIER: theorem/structure transport across carriers and proof contexts.
- SPACE: source/image/admissibility/boundary membership.
- REPRESENTATION: bidirectional representation with left/right inverse and observable-commutation proofs.
- LIMIT: diagram/index-filter/topology/limit-object convergence.
- SEMANTIC: formal-object to target-semantics correspondence under a frozen convention root.
- HERITAGE: MHP-1 semantic lineage, preservation, omission and verified derivation.

## Composition

`Valid(f) && Valid(g)` does not imply `Valid(g o f)`.

Composition requires:

1. authenticated predecessor receipts;
2. `target(f) == source(g)`;
3. composed outer endpoints equal the predecessor outer endpoints;
4. successful kind-specific verification of the composed subject;
5. a dedicated composition verifier/policy commitment and composition root.

## Evidence boundary

A well-formed hash is an identifier, not a proof. Every proof-bearing root used
by a kind-specific verifier must resolve through a trusted receipt store and be
bound to the exact subject it claims to verify.

`HERITAGE` remains an evidence-only Proof Trace kind. No morphism receipt may
advance a control-state root.

## Current repository admission status

This document describes the candidate implementation on its exact branch/PR
head. It does not claim merge, canonical admission, AGI, global Weil positivity,
or RH. Remote exact-head CI must pass before the candidate can be described as
verified at its head.
