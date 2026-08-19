# AEGIS Ω — Khatt–Abjad Capability Bridge v0.1

Status: DESIGN ONLY — implementation not yet established  
Design parent: `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`  
Branch: `feat/khatt-abjad-capability-bridge-v1`

## 1. Purpose

Connect the existing Gate 215 `Abjad Letter Encoder` to a canonical calligraphic-language observation contract without allowing visual/model interpretations to become authority.

The bridge is deliberately narrower than a full Arabic OCR or calligraphy model. v0.1 defines the deterministic boundary between an untrusted observation of Arabic-script graphemes and the existing integer Abjad transform.

Core invariant:

```text
visual/model observation != linguistic truth != authority != external effect
```

A model may propose readings. The bridge may deterministically encode those readings. Neither action proves that a reading is correct, authorizes a state transition, or proves an external effect.

## 2. Repository-bound starting point

At the design parent:

- `aegis-cl-psi/src/abjad_encoder.rs` is an implemented T2 Rust transform from pre-resolved `(abjad_value, dot_count)` letter specs into deterministic Abjad/routing records.
- `docs/GCCE_ARCHITECTURE.md` specifies the Khatt Loop vocabulary (`Nuqta -> Alif -> Rasm -> Tashkeel -> Tanasub`) and maps it to AEGIS concepts. This document is treated as architecture/specification, not as proof that every depicted module exists or that the mathematical analogies are established.
- `clients/gemma-edge-ios/Sources/GemmaEdge/KhattLoopValidation.swift` is an implemented fail-closed verdict parser around an `EdgeInferenceRunning` interface.
- `clients/gemma-edge-ios/README.md` states that the native inference backend is incomplete and the Swift package is not currently proven by monorepo CI.

The three surfaces are therefore related conceptually but are not yet one proven cross-runtime language pipeline.

## 3. Problem

Current Gate 215 input begins after the hardest epistemic step: the Arabic-script letters have already been resolved into Abjad values and dot counts.

Current Khatt validation accepts opaque `stateData: String` and returns a boolean model-verdict parse. It does not structurally represent graphemes, alternative readings, diacritics, ligatures, source modality, or provenance.

Without a shared contract, a future image/vision adapter could accidentally collapse:

```text
pixels -> guessed text -> Abjad encoding -> constitutional interpretation
```

into one opaque step. That would lose ambiguity and make it too easy to confuse deterministic arithmetic over a guessed reading with evidence that the reading itself is true.

## 4. Approaches considered

### A. Rust-first canonical observation bridge — RECOMMENDED

Define the canonical contract in `aegis-cl-psi`, because Gate 215 already owns the deterministic Abjad transform. Vision, Swift and TypeScript adapters emit the contract but do not own its semantics.

Advantages:
- smallest authority surface;
- reuses existing deterministic integer implementation;
- ambiguity can be preserved before any provider/model ranking;
- straightforward Rust unit tests and portable JSON vectors.

Cost:
- Swift/TypeScript consumers require follow-up adapters.

### B. Swift-first Khatt extension

Extend `KhattLoopValidation` to parse calligraphy and emit Abjad data.

Rejected for v0.1 because native inference is not yet established, the package is not in monorepo CI, and model output would sit too close to the constitutional verdict path.

### C. TypeScript coordinator-first bridge

Add the calligraphic contract to `sovereign-omega-v2` and invoke Gate 215 indirectly.

Rejected for v0.1 because it would duplicate the existing Rust source of deterministic Abjad arithmetic or introduce an unnecessary cross-runtime dependency before the data boundary is stable.

## 5. v0.1 architecture

```text
image | pen trajectory | Unicode | manual annotation
                       |
                       v
            untrusted modality adapter
                       |
                       v
          CalligraphicObservationV1
             /        |        \
       candidate A candidate B candidate C
             \        |        /
                       v
             KhattAbjadBridgeV1
                       |
        deterministic transform only
                       |
                       v
       AbjadCapabilityEncodingV1
          [encoded candidates...]
                       |
             NO candidate selection
             NO authority decision
             NO execution/effect claim
```

The bridge encodes every admissible reading candidate independently. It does not choose a winner.

## 6. Canonical input contract

`CalligraphicObservationV1` MUST contain:

- `record_kind = CALLIGRAPHIC_OBSERVATION_V1`
- `schema_version = 1.0.0`
- `source_digest` — lowercase SHA-256 of the source artifact or canonical source payload
- `source_modality` — one of:
  - `IMAGE`
  - `PEN_TRAJECTORY`
  - `UNICODE_TEXT`
  - `MANUAL_ANNOTATION`
- `script_family = ARABIC_SCRIPT`
- `reading_direction = RTL`
- one or more `reading_candidates`

Each reading candidate MUST contain:

- stable `candidate_id`
- `confidence_bps` in `[0,10000]`; observational metadata only
- ordered `graphemes`

Each grapheme MUST contain:

- `base_letter` — canonical Unicode string for the proposed letter identity
- `abjad_value > 0`
- `dot_count >= 0`
- `diacritics` — zero or more explicitly observed/proposed marks
- optional `source_region` or `trajectory_segment` reference

The schema MUST use `additionalProperties: false` at authority-sensitive levels.

The contract MUST NOT contain fields named or semantically equivalent to `authority`, `permit`, `execute`, `effect`, `success`, `decision_receipt`, `execution_receipt`, or `effect_receipt`.

## 7. Canonical output contract

`AbjadCapabilityEncodingV1` MUST contain:

- `record_kind = ABJAD_CAPABILITY_ENCODING_V1`
- `schema_version = 1.0.0`
- `derivation_kind = DETERMINISTIC_FROM_UNTRUSTED_OBSERVATION`
- `epistemic_ceiling = T2`
- `source_digest`
- `candidate_encodings[]`
- `ambiguity_preserved`

Each `candidate_encoding` binds the candidate ID to the deterministic Gate 215 result:

- letter records
- Abjad sum
- Abjad product
- sum/product digital roots
- sum/product families
- dodecagonal routing path
- name node
- self-reference flag as currently defined by Gate 215

The bridge MUST NOT emit a selected candidate ID in v0.1.

## 8. Provenance and hash domains

Use separate hash domains:

```text
AEGIS_CALLIGRAPHIC_OBSERVATION_V1
AEGIS_ABJAD_CAPABILITY_ENCODING_V1
```

A hash authenticates canonical bytes/integrity of the record. It does not prove that the visual or linguistic proposition is true.

No hash or Abjad-derived value may satisfy an AEGIS authority or effect verifier merely because it is deterministic.

## 9. Ambiguity preservation

If multiple candidate readings are supplied, all valid candidates must survive the bridge.

Required property:

```text
candidate_count_in == candidate_count_out
```

for all candidates that pass structural validation.

Provider confidence may order display/UI, but v0.1 core must not discard alternatives based on confidence.

This prevents:

```text
model confidence -> silent truth promotion
```

## 10. Stroke-order boundary

A static image cannot establish physical pen-stroke order.

Therefore:

```text
source_modality != PEN_TRAJECTORY
  => trajectory evidence MUST be absent
```

Even for `PEN_TRAJECTORY`, the bridge only records supplied trajectory evidence. It does not independently prove capture authenticity.

## 11. Khatt Loop relationship

v0.1 maps language evidence to Khatt terminology without treating the analogy as proof:

- `Nuqta` — atomic observed grapheme/dot evidence;
- `Rasm` — ordered base-letter skeleton;
- `Tashkeel` — explicit diacritics/uncertainty metadata;
- `Alif` — structural validation constraints;
- `Tanasub` — out of scope for linguistic truth in v0.1.

This mapping is architectural vocabulary only. It must not upgrade GCCE-local mathematical hypotheses into established language science.

## 12. Implementation slice after design approval

Planned files:

```text
aegis-cl-psi/src/abjad_capability_bridge.rs
schemas/calligraphic-observation.v1.schema.json
schemas/abjad-capability-encoding.v1.schema.json
test-vectors/calligraphic-language/arabic-v1.json
```

Existing file touched:

```text
aegis-cl-psi/src/lib.rs
```

`abjad_encoder.rs` should remain the arithmetic authority for the transform and should not be rewritten unless a test reveals a concrete defect.

No Swift or TypeScript runtime integration belongs in the first implementation commit. They consume the frozen schema/vector in a subsequent slice after Rust semantics are green.

## 13. Required tests

Before implementation is considered complete:

1. empty candidate set is rejected;
2. zero Abjad values are rejected through the existing Gate 215 boundary;
3. duplicate candidate IDs are rejected;
4. out-of-range confidence is rejected;
5. static-image observation cannot carry trajectory evidence;
6. two ambiguous readings produce two encoded readings;
7. candidate ordering is deterministic;
8. identical input produces identical output/hash;
9. Gate 215 encoding for `طارق` remains unchanged;
10. output cannot express authority, execution, or effect status;
11. schema rejects receipt-like fields;
12. canonical JSON vector round-trips without semantic drift.

## 14. Explicit non-goals

v0.1 does NOT establish:

- Arabic OCR accuracy;
- handwriting recognition accuracy;
- calligraphic style classification;
- historical manuscript interpretation;
- semantic correctness of any reading;
- pen trajectory authenticity;
- scientific significance of digital-root/vortex/dodecagonal mappings;
- provider/model authority;
- production deployment;
- effect proof.

## 15. Safety property

For every bridge output `b` derived from calligraphic observation `o`:

```text
b = Encode(o)
=>
b is evidence about a deterministic transformation of o
AND
b is not proof that o is linguistically true
AND
b is not authorization
AND
b is not proof of execution/effect
```

Or compactly:

```text
AbjadCapabilityEncodingV1 ∉ AuthorityEvidence
AbjadCapabilityEncodingV1 ∉ EffectEvidence
```

unless a future, separately admitted verifier explicitly defines and proves a narrower use. v0.1 defines no such promotion path.
