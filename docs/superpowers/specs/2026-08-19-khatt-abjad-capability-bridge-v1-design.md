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

## 3. External convention boundary

Abjad letter values are an external historical convention, not an AEGIS discovery. The bridge must version the convention explicitly.

Reference sources include Encyclopaedia Iranica, `ABJAD` (Georg Krotkoff), and Adam Gacek, *Arabic Manuscripts: A Vademecum for Readers*. These sources establish the historical use of Arabic letters as numerical values. They do not establish any AEGIS-local claim about digital roots, vortex families, dodecagonal routing, cognition, truth, or authority.

v0.1 supports the 28 base Arabic Abjad letters only. It does not silently assign values to Persian/Urdu extension letters or context-sensitive orthographic forms.

Every observation MUST declare one explicit system:

```text
MASHRIQI_V1
MAGHRIBI_V1
```

There is no default.

The Mashriqi table used by v0.1 is:

```text
ا=1   ب=2   ج=3   د=4   ه=5   و=6   ز=7   ح=8   ط=9   ي=10
ك=20  ل=30  م=40  ن=50  س=60  ع=70  ف=80  ص=90  ق=100 ر=200
ش=300 ت=400 ث=500 خ=600 ذ=700 ض=800 ظ=900 غ=1000
```

The Maghribi table differs for six letters:

```text
ص=60  ض=90  س=300  ظ=800  غ=900  ش=1000
```

All other supported base-letter values are identical to `MASHRIQI_V1`.

## 4. Problem

Current Gate 215 input begins after the hardest epistemic step: the Arabic-script letters have already been resolved into Abjad values and dot counts.

Current Khatt validation accepts opaque `stateData: String` and returns a boolean model-verdict parse. It does not structurally represent graphemes, alternative readings, diacritics, ligatures, source modality, provenance, or the selected Abjad convention.

Without a shared contract, a future image/vision adapter could accidentally collapse:

```text
pixels -> guessed text -> Abjad encoding -> constitutional interpretation
```

into one opaque step. That would lose ambiguity and make it too easy to confuse deterministic arithmetic over a guessed reading with evidence that the reading itself is true.

A second failure mode is accepting both `base_letter` and an arbitrary caller-supplied `abjad_value`. A model could then claim one letter while supplying another letter's number. v0.1 prohibits this: Abjad values are derived by the bridge from a versioned canonical mapping and are never trusted from the observation payload.

## 5. Approaches considered

### A. Rust-first canonical observation bridge — RECOMMENDED

Define the canonical contract in `aegis-cl-psi`, because Gate 215 already owns the deterministic Abjad transform. Vision, Swift and TypeScript adapters emit the contract but do not own its Abjad arithmetic.

Advantages:
- smallest authority surface;
- reuses existing deterministic integer implementation;
- ambiguity can be preserved before any provider/model ranking;
- letter/value mismatches become structurally impossible;
- straightforward Rust unit tests and portable JSON vectors.

Cost:
- Swift/TypeScript consumers require follow-up adapters.

### B. Swift-first Khatt extension

Extend `KhattLoopValidation` to parse calligraphy and emit Abjad data.

Rejected for v0.1 because native inference is not yet established, the package is not in monorepo CI, and model output would sit too close to the constitutional verdict path.

### C. TypeScript coordinator-first bridge

Add the calligraphic contract to `sovereign-omega-v2` and invoke Gate 215 indirectly.

Rejected for v0.1 because it would duplicate the existing Rust source of deterministic Abjad arithmetic or introduce an unnecessary cross-runtime dependency before the data boundary is stable.

## 6. v0.1 architecture

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
               |             |
               |       ArabicAbjadSystemV1
               |       letter -> integer
               v             v
            existing Gate 215 encoder
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

## 7. Canonical input contract

`CalligraphicObservationV1` MUST contain:

- `record_kind = CALLIGRAPHIC_OBSERVATION_V1`
- `schema_version = 1.0.0`
- `source_digest` — lowercase SHA-256 of the original source bytes or an explicitly defined source payload
- `source_modality` — one of:
  - `IMAGE`
  - `PEN_TRAJECTORY`
  - `UNICODE_TEXT`
  - `MANUAL_ANNOTATION`
- `script_family = ARABIC_SCRIPT`
- `reading_direction = RTL`
- `abjad_system` — `MASHRIQI_V1` or `MAGHRIBI_V1`
- one or more `reading_candidates`

Each reading candidate MUST contain:

- stable `candidate_id`
- `confidence_bps` in `[0,10000]`; observational metadata only
- ordered `graphemes`

Each grapheme MUST contain:

- `surface_form` — the observed/proposed surface representation, preserved for provenance;
- `abjad_letter` — exactly one canonical base letter from the supported 28-letter enum;
- `dot_count` in `[0,3]`;
- `dot_evidence` — one of `OBSERVED`, `INFERRED`, `NOT_VISIBLE`;
- `diacritics` — zero or more explicit marks, preserved as metadata;
- optional `source_region` or `trajectory_segment` reference.

The observation MUST NOT contain an `abjad_value` field. The bridge derives the value from `(abjad_system, abjad_letter)`.

`surface_form` and all textual metadata must be valid UTF-8 and NFC-normalized before admission to the deterministic bridge. The bridge does not silently reinterpret Arabic Presentation Forms or unsupported letters as a base Abjad letter; the modality adapter must make that interpretation explicit in `abjad_letter` and preserve the original surface in `surface_form`.

The schema MUST use `additionalProperties: false` at authority-sensitive levels.

The contract MUST NOT contain fields named or semantically equivalent to `authority`, `permit`, `execute`, `effect`, `success`, `decision_receipt`, `execution_receipt`, or `effect_receipt`.

## 8. Canonical output contract

`AbjadCapabilityEncodingV1` MUST contain:

- `record_kind = ABJAD_CAPABILITY_ENCODING_V1`
- `schema_version = 1.0.0`
- `derivation_kind = DETERMINISTIC_FROM_UNTRUSTED_OBSERVATION`
- `epistemic_ceiling = T2`
- `source_digest`
- `abjad_system`
- `candidate_encodings[]`
- `ambiguity_preserved`

Each `candidate_encoding` binds the candidate ID to the deterministic Gate 215 result and preserves the input grapheme metadata:

- canonical base letters;
- derived Abjad values;
- surface forms;
- dot evidence;
- diacritics;
- Gate 215 letter records;
- Abjad sum;
- Abjad product;
- sum/product digital roots;
- sum/product families;
- dodecagonal routing path;
- name node;
- self-reference flag as currently defined by Gate 215.

The bridge MUST NOT emit a selected candidate ID in v0.1.

## 9. Digest boundary

v0.1 binds every observation/output to `source_digest`, which is SHA-256 over the original source bytes or an explicitly defined non-JSON source payload.

v0.1 deliberately does NOT introduce a cross-runtime hash of the JSON observation or output record. The repository's cross-runtime canonical-JSON boundary must be separately established before such a digest can be authoritative or parity-tested across Rust, Swift and TypeScript.

Therefore:

```text
source_digest proves byte identity of the supplied source artifact
source_digest does not prove the reading is correct
Abjad arithmetic does not prove the reading is correct
```

A later revision may add a domain-separated record digest only after the canonicalization format is frozen and cross-runtime vectors pass.

## 10. Ambiguity preservation

If multiple candidate readings are supplied, all structurally valid candidates must survive the bridge.

Required property:

```text
candidate_count_in == candidate_count_out
```

The core preserves exact input candidate order. It does not reorder, select, or discard candidates by confidence. A UI may display a separately sorted view, but that cannot mutate the canonical bridge output.

This prevents:

```text
model confidence -> silent truth promotion
```

## 11. Stroke-order boundary

A static image cannot establish physical pen-stroke order.

Therefore:

```text
source_modality != PEN_TRAJECTORY
  => trajectory_segment MUST be absent
```

Even for `PEN_TRAJECTORY`, the bridge only records supplied trajectory evidence. It does not independently prove capture authenticity.

## 12. Diacritic and dot boundary

Diacritics and dot evidence are first-class observation metadata but do not alter Abjad values in v0.1.

`dot_evidence = NOT_VISIBLE` is distinct from `dot_count = 0`: the former says the source did not make the dot evidence available; the latter is the proposed count attached to the candidate reading. This distinction prevents an unreadable or historically undotted glyph from being silently treated as evidence of a genuinely dotless letter.

The bridge may report consistency diagnostics in a future revision, but v0.1 must not reject a reading merely because historical or calligraphic dot practice differs from a modern canonical glyph.

## 13. Khatt Loop relationship

v0.1 maps language evidence to Khatt terminology without treating the analogy as proof:

- `Nuqta` — atomic observed grapheme/dot evidence;
- `Rasm` — ordered base-letter skeleton;
- `Tashkeel` — explicit diacritics/uncertainty metadata;
- `Alif` — structural validation constraints;
- `Tanasub` — out of scope for linguistic truth in v0.1.

This mapping is architectural vocabulary only. It must not upgrade GCCE-local mathematical hypotheses into established language science.

## 14. Implementation slice after design approval

Planned new files:

```text
aegis-cl-psi/src/arabic_abjad.rs
aegis-cl-psi/src/abjad_capability_bridge.rs
schemas/calligraphic-observation.v1.schema.json
schemas/abjad-capability-encoding.v1.schema.json
test-vectors/calligraphic-language/arabic-v1.json
```

Existing file touched:

```text
aegis-cl-psi/src/lib.rs
```

`abjad_encoder.rs` remains the arithmetic transform used by the bridge and should not be rewritten unless a failing regression test reveals a concrete defect.

No Swift or TypeScript runtime integration belongs in the first implementation commit. They consume the frozen schema/vector in a subsequent slice after Rust semantics are green.

## 15. Required tests

Before implementation is considered complete:

1. empty candidate set is rejected;
2. unsupported/non-base Abjad letter is rejected;
3. caller-supplied `abjad_value` is impossible in the typed Rust input and rejected by JSON schema;
4. duplicate candidate IDs are rejected;
5. out-of-range confidence is rejected;
6. static-image observation cannot carry trajectory segments;
7. two ambiguous readings produce two encoded readings in the same order;
8. identical typed input produces identical typed output;
9. Gate 215 encoding for `طارق` remains unchanged under `MASHRIQI_V1`;
10. `س` encodes as 60 under `MASHRIQI_V1` and 300 under `MAGHRIBI_V1`;
11. omission of `abjad_system` is rejected; there is no default;
12. `dot_evidence = NOT_VISIBLE` remains distinguishable from a visible zero-dot glyph;
13. output cannot express authority, execution, or effect status;
14. schema rejects receipt-like fields;
15. JSON fixture round-trips without semantic drift;
16. existing Gate 215 tests remain green.

## 16. Explicit non-goals

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
- effect proof;
- a value convention for Persian/Urdu extension letters;
- a universal normalization rule for hamza, tāʾ marbūṭa, alif maqṣūra, ligatures, or other context-sensitive orthographic forms.

Those forms may appear in `surface_form`, but a candidate must explicitly bind them to one supported base `abjad_letter` before v0.1 will encode them.

## 17. Safety property

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

Compactly:

```text
AbjadCapabilityEncodingV1 ∉ AuthorityEvidence
AbjadCapabilityEncodingV1 ∉ EffectEvidence
```

unless a future, separately admitted verifier explicitly defines and proves a narrower use. v0.1 defines no such promotion path.
