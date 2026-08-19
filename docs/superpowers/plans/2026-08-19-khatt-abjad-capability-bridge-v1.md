# Khatt–Abjad Capability Bridge v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic Rust bridge from explicitly untrusted Arabic-script reading candidates into the existing Gate 215 Abjad encoder while preserving ambiguity and preventing any authority/effect interpretation.

**Architecture:** Add one versioned Arabic Abjad convention module and one typed bridge module inside `aegis-cl-psi`. The bridge validates observation structure, derives numeric values from canonical base letters, preserves candidate order, and delegates arithmetic to existing `abjad_encoder::encode`. JSON schemas and a portable fixture mirror the Rust boundary but do not introduce a new cross-runtime record hash.

**Tech Stack:** Rust 2021, serde/serde_json, `unicode-normalization` for NFC validation, JSON Schema Draft 2020-12, existing CL-Ψ CI (`cargo test --jobs 1 -- --test-threads 1`).

**Spec:** `docs/superpowers/specs/2026-08-19-khatt-abjad-capability-bridge-v1-design.md`

## Global Constraints

- Parent is canonical `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`; implementation remains isolated on `feat/khatt-abjad-capability-bridge-v1`.
- Existing `aegis-cl-psi/src/abjad_encoder.rs` remains the arithmetic transform; do not duplicate its routing/digital-root logic.
- `CalligraphicObservationV1` is untrusted evidence only; no model/provider field may confer authority.
- There is no default Abjad convention. Callers must choose `MASHRIQI_V1` or `MAGHRIBI_V1`.
- Caller-supplied numeric Abjad values are forbidden. Values are derived from `(abjad_system, abjad_letter)`.
- Static image input cannot carry trajectory evidence.
- Candidate order and candidate count are preserved exactly; core logic never chooses a winning reading.
- Output has epistemic ceiling T2 and cannot represent authorization, execution success, or effect proof.
- No Swift/TypeScript runtime integration in this slice.
- No scientific claim is made for digital-root/vortex/dodecagonal interpretations beyond deterministic computation already implemented by Gate 215.

---

### Task 1: Versioned Arabic Abjad convention

**Files:**
- Create: `aegis-cl-psi/src/arabic_abjad.rs`
- Modify: `aegis-cl-psi/src/lib.rs`

**Interfaces:**
- Produces `ArabicAbjadSystem::{MashriqiV1, MaghribiV1}`.
- Produces `ArabicAbjadLetter` enum containing exactly the 28 supported base letters.
- Produces `ArabicAbjadLetter::as_str() -> &'static str`.
- Produces `abjad_value(system: ArabicAbjadSystem, letter: ArabicAbjadLetter) -> u64`.

- [ ] **Step 1: Write failing unit tests in `arabic_abjad.rs`**

Tests must assert at minimum:

```rust
#[test]
fn seen_differs_between_systems() {
    assert_eq!(abjad_value(ArabicAbjadSystem::MashriqiV1, ArabicAbjadLetter::Seen), 60);
    assert_eq!(abjad_value(ArabicAbjadSystem::MaghribiV1, ArabicAbjadLetter::Seen), 300);
}

#[test]
fn tariq_values_match_gate_215() {
    let values = [
        ArabicAbjadLetter::Tah,
        ArabicAbjadLetter::Alif,
        ArabicAbjadLetter::Ra,
        ArabicAbjadLetter::Qaf,
    ].map(|letter| abjad_value(ArabicAbjadSystem::MashriqiV1, letter));
    assert_eq!(values, [9, 1, 200, 100]);
}
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
cd aegis-cl-psi
cargo test arabic_abjad --jobs 1 -- --test-threads 1
```

Expected: compile failure because the new module/API does not yet exist.

- [ ] **Step 3: Implement the minimal canonical mapping**

Use serde-stable enum names:

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ArabicAbjadSystem {
    MashriqiV1,
    MaghribiV1,
}
```

`ArabicAbjadLetter` must serialize to the actual canonical Arabic base glyph (`"ا"`, `"ب"`, …) using explicit `#[serde(rename = "...")]` attributes rather than relying on enum variant names. Implement the Mashriqi table exactly as frozen in the spec and override only `ص ض س ظ غ ش` for Maghribi.

- [ ] **Step 4: Export modules from `lib.rs` and verify GREEN**

Add immediately after Gate 215:

```rust
// Khatt–Abjad v0.1 — versioned historical convention + evidence bridge (T2)
pub mod arabic_abjad;
pub mod abjad_capability_bridge;
```

Until Task 2 creates the bridge file, export only `arabic_abjad`; add `abjad_capability_bridge` in Task 2 to keep each commit compiling.

Run:

```bash
cd aegis-cl-psi
cargo test arabic_abjad --jobs 1 -- --test-threads 1
cargo test abjad_encoder --jobs 1 -- --test-threads 1
```

Expected: all focused tests pass; existing Gate 215 Tariq tests remain unchanged.

- [ ] **Step 5: Commit**

```bash
git add aegis-cl-psi/src/arabic_abjad.rs aegis-cl-psi/src/lib.rs
git commit -m "feat(language): add versioned Arabic Abjad mapping"
```

---

### Task 2: Typed untrusted-observation bridge

**Files:**
- Create: `aegis-cl-psi/src/abjad_capability_bridge.rs`
- Modify: `aegis-cl-psi/src/lib.rs`
- Modify: `aegis-cl-psi/Cargo.toml`
- Regenerate: `aegis-cl-psi/Cargo.lock`

**Interfaces:**
- Consumes `ArabicAbjadSystem`, `ArabicAbjadLetter`, and `abjad_value` from Task 1.
- Consumes existing `crate::abjad_encoder::encode`.
- Produces `bridge_observation(observation: &CalligraphicObservationV1) -> Result<AbjadCapabilityEncodingV1, BridgeError>`.
- Produces serde-serializable/deserializable input/output records without authority/effect fields.

- [ ] **Step 1: Add dependency and write RED tests**

Add:

```toml
unicode-normalization = "0.1"
```

Define tests first for:

```rust
empty_candidates_are_rejected()
duplicate_candidate_ids_are_rejected()
confidence_over_10000_is_rejected()
non_nfc_surface_is_rejected()
static_image_with_trajectory_is_rejected()
ambiguous_candidates_preserve_order()
tariq_bridge_matches_gate_215()
not_visible_dot_evidence_is_preserved()
identical_input_produces_identical_output()
```

Use a helper observation with a fixed 64-hex `source_digest`, `SourceModality::ManualAnnotation`, `ArabicAbjadSystem::MashriqiV1`, and explicit graphemes.

- [ ] **Step 2: Run focused bridge tests and verify RED**

```bash
cd aegis-cl-psi
cargo test abjad_capability_bridge --jobs 1 -- --test-threads 1
```

Expected: compile/test failure because types/bridge behavior are absent.

- [ ] **Step 3: Implement the typed input boundary**

Required core enums/types:

```rust
pub const CALLIGRAPHIC_OBSERVATION_KIND: &str = "CALLIGRAPHIC_OBSERVATION_V1";
pub const ABJAD_CAPABILITY_ENCODING_KIND: &str = "ABJAD_CAPABILITY_ENCODING_V1";
pub const SCHEMA_VERSION: &str = "1.0.0";

pub enum SourceModality { Image, PenTrajectory, UnicodeText, ManualAnnotation }
pub enum DotEvidence { Observed, Inferred, NotVisible }

pub struct GraphemeObservation {
    pub surface_form: String,
    pub abjad_letter: ArabicAbjadLetter,
    pub dot_count: u8,
    pub dot_evidence: DotEvidence,
    pub diacritics: Vec<String>,
    pub source_region: Option<String>,
    pub trajectory_segment: Option<String>,
}

pub struct ReadingCandidate {
    pub candidate_id: String,
    pub confidence_bps: u16,
    pub graphemes: Vec<GraphemeObservation>,
}

pub struct CalligraphicObservationV1 {
    pub record_kind: String,
    pub schema_version: String,
    pub source_digest: String,
    pub source_modality: SourceModality,
    pub script_family: String,
    pub reading_direction: String,
    pub abjad_system: ArabicAbjadSystem,
    pub reading_candidates: Vec<ReadingCandidate>,
}
```

Validation must fail closed on wrong discriminators, malformed digest, empty candidates/graphemes, duplicate/empty IDs, confidence > 10000, dot_count > 3, non-NFC textual fields/diacritics, and any trajectory segment when modality is not `PEN_TRAJECTORY`.

Use:

```rust
use unicode_normalization::UnicodeNormalization;
fn is_nfc(value: &str) -> bool { value.nfc().eq(value.chars()) }
```

- [ ] **Step 4: Implement deterministic delegation to Gate 215**

For each candidate, build `Vec<LetterSpec>` only from canonical values:

```rust
let specs = candidate.graphemes.iter()
    .map(|g| (abjad_value(observation.abjad_system, g.abjad_letter), g.dot_count))
    .collect::<Vec<_>>();
let gate215 = crate::abjad_encoder::encode(&specs)
    .map_err(|_| BridgeError::Gate215Rejected)?;
```

Copy the deterministic Gate 215 result into a serializable output DTO; do not alter/recompute its routing semantics. Preserve input candidate order and all grapheme observation metadata. Set:

```rust
record_kind = "ABJAD_CAPABILITY_ENCODING_V1"
derivation_kind = "DETERMINISTIC_FROM_UNTRUSTED_OBSERVATION"
epistemic_ceiling = "T2"
ambiguity_preserved = reading_candidates.len() > 1
```

No `selected_candidate`, `authority`, `decision`, `execution`, `effect`, `success`, or receipt field exists in the Rust output type.

- [ ] **Step 5: Verify focused and full CL-Ψ suites**

```bash
cd aegis-cl-psi
cargo test abjad_capability_bridge --jobs 1 -- --test-threads 1
cargo test arabic_abjad --jobs 1 -- --test-threads 1
cargo test abjad_encoder --jobs 1 -- --test-threads 1
cargo test --jobs 1 -- --test-threads 1
```

Expected: all green and total test count remains at or above CI floor 6800.

- [ ] **Step 6: Commit**

```bash
git add aegis-cl-psi/src/abjad_capability_bridge.rs aegis-cl-psi/src/lib.rs aegis-cl-psi/Cargo.toml aegis-cl-psi/Cargo.lock
git commit -m "feat(language): bridge calligraphic observations to Gate 215"
```

---

### Task 3: JSON schemas and portable test vector

**Files:**
- Create: `schemas/calligraphic-observation.v1.schema.json`
- Create: `schemas/abjad-capability-encoding.v1.schema.json`
- Create: `test-vectors/calligraphic-language/arabic-v1.json`
- Add tests in: `aegis-cl-psi/src/abjad_capability_bridge.rs`

**Interfaces:**
- JSON keys/enum spellings must exactly match serde output from Task 2.
- Fixture contains one valid observation plus expected deterministic bridge output for `طارق` and one ambiguity example.

- [ ] **Step 1: Write schema-validation tests before schema files**

Inside Rust tests, load schemas with `include_str!("../../schemas/...")` only for syntax/contract assertions that can be performed with `serde_json`; do not add a heavyweight runtime JSON-schema validator to the Rust crate. Assert exact `record_kind` consts, required `abjad_system`, `additionalProperties: false`, absence of `abjad_value` in observation schema, and absence of authority/receipt property names in output schema.

- [ ] **Step 2: Verify RED because schema files do not exist**

```bash
cd aegis-cl-psi
cargo test schema_contract --jobs 1 -- --test-threads 1
```

Expected: compile failure from missing `include_str!` targets.

- [ ] **Step 3: Create input schema**

Use Draft 2020-12. Top-level requirements include:

```json
"record_kind": {"const":"CALLIGRAPHIC_OBSERVATION_V1"},
"schema_version": {"const":"1.0.0"},
"source_digest": {"type":"string","pattern":"^[0-9a-f]{64}$"},
"source_modality": {"enum":["IMAGE","PEN_TRAJECTORY","UNICODE_TEXT","MANUAL_ANNOTATION"]},
"script_family": {"const":"ARABIC_SCRIPT"},
"reading_direction": {"const":"RTL"},
"abjad_system": {"enum":["MASHRIQI_V1","MAGHRIBI_V1"]}
```

Define exactly 28 canonical Arabic `abjad_letter` enum values. `additionalProperties: false` at top level, candidate, and grapheme objects makes `abjad_value` and receipt-like injections invalid.

Use JSON Schema `if/then` so `trajectory_segment` is only allowed when top-level modality is `PEN_TRAJECTORY`; mirror this with the Rust validator because schemas alone are not the runtime authority.

- [ ] **Step 4: Create output schema**

Require const discriminators and fixed boundaries:

```json
"record_kind": {"const":"ABJAD_CAPABILITY_ENCODING_V1"},
"schema_version": {"const":"1.0.0"},
"derivation_kind": {"const":"DETERMINISTIC_FROM_UNTRUSTED_OBSERVATION"},
"epistemic_ceiling": {"const":"T2"}
```

Expose only evidence/encoding fields. There is no selected candidate and no authority/execution/effect/receipt vocabulary.

- [ ] **Step 5: Create fixture and round-trip test**

Fixture must contain:

- Mashriqi `طارق` candidate with expected derived values `[9,1,200,100]`, sum `310`, product `180000`, name node `10`.
- A two-candidate ambiguous example whose output candidate IDs remain in input order.
- A `NOT_VISIBLE` dot-evidence example proving it remains distinct from `dot_count: 0`.

Rust test parses fixture observation via `serde_json`, calls `bridge_observation`, serializes result, and compares the deterministic fields to fixture expectations.

- [ ] **Step 6: Run all verification**

```bash
python -m json.tool schemas/calligraphic-observation.v1.schema.json >/dev/null
python -m json.tool schemas/abjad-capability-encoding.v1.schema.json >/dev/null
python -m json.tool test-vectors/calligraphic-language/arabic-v1.json >/dev/null
cd aegis-cl-psi
cargo test --jobs 1 -- --test-threads 1
```

Expected: valid JSON and complete CL-Ψ suite green.

- [ ] **Step 7: Commit**

```bash
git add schemas/calligraphic-observation.v1.schema.json schemas/abjad-capability-encoding.v1.schema.json test-vectors/calligraphic-language/arabic-v1.json aegis-cl-psi/src/abjad_capability_bridge.rs
git commit -m "test(language): freeze Khatt-Abjad schemas and vectors"
```

---

### Task 4: Exact-head PR admission evidence

**Files:** no new implementation files unless CI reveals a concrete defect.

**Interfaces:** GitHub PR targets canonical `main`; CI must exercise the exact branch head.

- [ ] **Step 1: Re-fetch canonical main and branch head**

Require canonical main still equals the design parent or explicitly report/reconcile a moved base before claiming exact-parent admission.

- [ ] **Step 2: Open a draft PR**

Title:

```text
feat(language): Khatt-Abjad capability bridge v0.1
```

Body must state: T2 evidence bridge; no OCR/semantic accuracy claim; no authority/effect path; reuses Gate 215; Swift/TS integration deferred.

- [ ] **Step 3: Read exact-head CI, not mergeability alone**

At minimum inspect the Constitutional Automaton CL-Ψ job and any schema/security checks. Do not claim PASS until GitHub reports success on the final head SHA.

- [ ] **Step 4: If CI fails, debug the first concrete failure only**

Use systematic-debugging: reproduce evidence from logs, patch the narrow root cause, then re-run exact-head verification. Do not weaken gates or thresholds to get green.

- [ ] **Step 5: Completion evidence**

Report final head SHA, base SHA, test/CI outcomes, remaining NOT_ESTABLISHED boundaries, and leave PR draft unless separately authorized to change review/merge state.
