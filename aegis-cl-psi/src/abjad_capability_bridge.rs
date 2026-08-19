//! Khatt–Abjad capability bridge v0.1.
//!
//! EPISTEMIC TIER: T2 (engineering evidence transform).
//!
//! The bridge validates an explicitly untrusted Arabic-script observation, derives
//! canonical Abjad integers from the selected versioned convention, and delegates
//! arithmetic/routing to Gate 215. It preserves ambiguity and has no authority,
//! execution-success, or effect-proof semantics.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};
use unicode_normalization::UnicodeNormalization;

use crate::abjad_encoder;
use crate::arabic_abjad::{abjad_value, ArabicAbjadLetter, ArabicAbjadSystem};
use crate::vortex_classifier::VortexFamily;

pub const CALLIGRAPHIC_OBSERVATION_KIND: &str = "CALLIGRAPHIC_OBSERVATION_V1";
pub const ABJAD_CAPABILITY_ENCODING_KIND: &str = "ABJAD_CAPABILITY_ENCODING_V1";
pub const SCHEMA_VERSION: &str = "1.0.0";
pub const DERIVATION_KIND: &str = "DETERMINISTIC_FROM_UNTRUSTED_OBSERVATION";
pub const EPISTEMIC_CEILING: &str = "T2";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SourceModality {
    Image,
    PenTrajectory,
    UnicodeText,
    ManualAnnotation,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum DotEvidence {
    Observed,
    Inferred,
    NotVisible,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GraphemeObservation {
    pub surface_form: String,
    pub abjad_letter: ArabicAbjadLetter,
    pub dot_count: u8,
    pub dot_evidence: DotEvidence,
    pub diacritics: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_region: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trajectory_segment: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReadingCandidate {
    pub candidate_id: String,
    pub confidence_bps: u16,
    pub graphemes: Vec<GraphemeObservation>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
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

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum VortexFamilyLabel {
    Triadic,
    Hexadic,
}

impl From<VortexFamily> for VortexFamilyLabel {
    fn from(value: VortexFamily) -> Self {
        match value {
            VortexFamily::Triadic => Self::Triadic,
            VortexFamily::Hexadic => Self::Hexadic,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EncodedLetterRecord {
    pub abjad_value: u64,
    pub digital_root: u8,
    pub family: VortexFamilyLabel,
    pub dodecagon_node: u8,
    pub opposite_node: u8,
    pub dot_count: u8,
    pub cycle_length: Option<u8>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CandidateEncodingV1 {
    pub candidate_id: String,
    pub confidence_bps: u16,
    pub graphemes: Vec<GraphemeObservation>,
    pub derived_abjad_values: Vec<u64>,
    pub letter_records: Vec<EncodedLetterRecord>,
    pub abjad_sum: u64,
    pub abjad_product: u64,
    pub sum_dr: u8,
    pub product_dr: u8,
    pub sum_family: VortexFamilyLabel,
    pub product_family: VortexFamilyLabel,
    pub name_node: u8,
    pub routing_path: Vec<u8>,
    pub is_self_referential: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AbjadCapabilityEncodingV1 {
    pub record_kind: String,
    pub schema_version: String,
    pub derivation_kind: String,
    pub epistemic_ceiling: String,
    pub source_digest: String,
    pub abjad_system: ArabicAbjadSystem,
    pub candidate_encodings: Vec<CandidateEncodingV1>,
    pub ambiguity_preserved: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BridgeError {
    InvalidRecordKind,
    UnsupportedSchema,
    InvalidSourceDigest,
    InvalidScriptFamily,
    InvalidReadingDirection,
    EmptyCandidates,
    EmptyCandidateId,
    DuplicateCandidateId,
    ConfidenceOutOfRange,
    EmptyGraphemeSequence,
    EmptySurfaceForm,
    DotCountOutOfRange,
    NonNfcText,
    TrajectoryWithoutPenSource,
    Gate215Rejected,
}

fn is_lower_hex_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn is_nfc(value: &str) -> bool {
    value.nfc().eq(value.chars())
}

fn validate_text(value: &str) -> Result<(), BridgeError> {
    if !is_nfc(value) {
        return Err(BridgeError::NonNfcText);
    }
    Ok(())
}

fn validate_observation(observation: &CalligraphicObservationV1) -> Result<(), BridgeError> {
    if observation.record_kind != CALLIGRAPHIC_OBSERVATION_KIND {
        return Err(BridgeError::InvalidRecordKind);
    }
    if observation.schema_version != SCHEMA_VERSION {
        return Err(BridgeError::UnsupportedSchema);
    }
    if !is_lower_hex_sha256(&observation.source_digest) {
        return Err(BridgeError::InvalidSourceDigest);
    }
    if observation.script_family != "ARABIC_SCRIPT" {
        return Err(BridgeError::InvalidScriptFamily);
    }
    if observation.reading_direction != "RTL" {
        return Err(BridgeError::InvalidReadingDirection);
    }
    if observation.reading_candidates.is_empty() {
        return Err(BridgeError::EmptyCandidates);
    }

    let mut candidate_ids = BTreeSet::new();
    for candidate in &observation.reading_candidates {
        if candidate.candidate_id.is_empty() {
            return Err(BridgeError::EmptyCandidateId);
        }
        validate_text(&candidate.candidate_id)?;
        if !candidate_ids.insert(candidate.candidate_id.as_str()) {
            return Err(BridgeError::DuplicateCandidateId);
        }
        if candidate.confidence_bps > 10_000 {
            return Err(BridgeError::ConfidenceOutOfRange);
        }
        if candidate.graphemes.is_empty() {
            return Err(BridgeError::EmptyGraphemeSequence);
        }

        for grapheme in &candidate.graphemes {
            if grapheme.surface_form.is_empty() {
                return Err(BridgeError::EmptySurfaceForm);
            }
            validate_text(&grapheme.surface_form)?;
            if grapheme.dot_count > 3 {
                return Err(BridgeError::DotCountOutOfRange);
            }
            for diacritic in &grapheme.diacritics {
                validate_text(diacritic)?;
            }
            if let Some(region) = &grapheme.source_region {
                validate_text(region)?;
            }
            if let Some(segment) = &grapheme.trajectory_segment {
                validate_text(segment)?;
                if observation.source_modality != SourceModality::PenTrajectory {
                    return Err(BridgeError::TrajectoryWithoutPenSource);
                }
            }
        }
    }

    Ok(())
}

/// Deterministically encode every structurally admissible reading candidate.
///
/// Candidate order and count are preserved. Confidence is copied as observational
/// metadata and never used for candidate selection or authority.
pub fn bridge_observation(
    observation: &CalligraphicObservationV1,
) -> Result<AbjadCapabilityEncodingV1, BridgeError> {
    validate_observation(observation)?;

    let mut candidate_encodings = Vec::with_capacity(observation.reading_candidates.len());
    for candidate in &observation.reading_candidates {
        let derived_abjad_values = candidate
            .graphemes
            .iter()
            .map(|grapheme| abjad_value(observation.abjad_system, grapheme.abjad_letter))
            .collect::<Vec<_>>();
        let specs = candidate
            .graphemes
            .iter()
            .zip(derived_abjad_values.iter().copied())
            .map(|(grapheme, value)| (value, grapheme.dot_count))
            .collect::<Vec<_>>();

        let gate215 = abjad_encoder::encode(&specs).map_err(|_| BridgeError::Gate215Rejected)?;
        let letter_records = gate215
            .letters
            .iter()
            .map(|record| EncodedLetterRecord {
                abjad_value: record.abjad_value,
                digital_root: record.digital_root,
                family: record.family.into(),
                dodecagon_node: record.dodecagon_node,
                opposite_node: record.opposite_node,
                dot_count: record.dot_count,
                cycle_length: record.cycle_length,
            })
            .collect();

        candidate_encodings.push(CandidateEncodingV1 {
            candidate_id: candidate.candidate_id.clone(),
            confidence_bps: candidate.confidence_bps,
            graphemes: candidate.graphemes.clone(),
            derived_abjad_values,
            letter_records,
            abjad_sum: gate215.abjad_sum,
            abjad_product: gate215.abjad_product,
            sum_dr: gate215.sum_dr,
            product_dr: gate215.product_dr,
            sum_family: gate215.sum_family.into(),
            product_family: gate215.product_family.into(),
            name_node: gate215.name_node,
            routing_path: gate215.routing_path,
            is_self_referential: gate215.is_self_referential,
        });
    }

    Ok(AbjadCapabilityEncodingV1 {
        record_kind: ABJAD_CAPABILITY_ENCODING_KIND.to_owned(),
        schema_version: SCHEMA_VERSION.to_owned(),
        derivation_kind: DERIVATION_KIND.to_owned(),
        epistemic_ceiling: EPISTEMIC_CEILING.to_owned(),
        source_digest: observation.source_digest.clone(),
        abjad_system: observation.abjad_system,
        ambiguity_preserved: candidate_encodings.len() > 1,
        candidate_encodings,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::arabic_abjad::{ArabicAbjadLetter, ArabicAbjadSystem};

    const SOURCE_DIGEST: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

    fn grapheme(letter: ArabicAbjadLetter, surface: &str, dots: u8) -> GraphemeObservation {
        GraphemeObservation {
            surface_form: surface.to_owned(),
            abjad_letter: letter,
            dot_count: dots,
            dot_evidence: DotEvidence::Observed,
            diacritics: Vec::new(),
            source_region: None,
            trajectory_segment: None,
        }
    }

    fn candidate(id: &str, confidence_bps: u16, graphemes: Vec<GraphemeObservation>) -> ReadingCandidate {
        ReadingCandidate {
            candidate_id: id.to_owned(),
            confidence_bps,
            graphemes,
        }
    }

    fn observation(candidates: Vec<ReadingCandidate>) -> CalligraphicObservationV1 {
        CalligraphicObservationV1 {
            record_kind: CALLIGRAPHIC_OBSERVATION_KIND.to_owned(),
            schema_version: SCHEMA_VERSION.to_owned(),
            source_digest: SOURCE_DIGEST.to_owned(),
            source_modality: SourceModality::ManualAnnotation,
            script_family: "ARABIC_SCRIPT".to_owned(),
            reading_direction: "RTL".to_owned(),
            abjad_system: ArabicAbjadSystem::MashriqiV1,
            reading_candidates: candidates,
        }
    }

    fn tariq_candidate(id: &str) -> ReadingCandidate {
        candidate(
            id,
            10_000,
            vec![
                grapheme(ArabicAbjadLetter::Tah, "ط", 0),
                grapheme(ArabicAbjadLetter::Alif, "ا", 0),
                grapheme(ArabicAbjadLetter::Ra, "ر", 0),
                grapheme(ArabicAbjadLetter::Qaf, "ق", 2),
            ],
        )
    }

    #[test]
    fn empty_candidates_are_rejected() {
        let error = bridge_observation(&observation(Vec::new())).unwrap_err();
        assert_eq!(error, BridgeError::EmptyCandidates);
    }

    #[test]
    fn duplicate_candidate_ids_are_rejected() {
        let input = observation(vec![tariq_candidate("same"), tariq_candidate("same")]);
        let error = bridge_observation(&input).unwrap_err();
        assert_eq!(error, BridgeError::DuplicateCandidateId);
    }

    #[test]
    fn confidence_over_10000_is_rejected() {
        let input = observation(vec![candidate(
            "too-confident",
            10_001,
            vec![grapheme(ArabicAbjadLetter::Alif, "ا", 0)],
        )]);
        let error = bridge_observation(&input).unwrap_err();
        assert_eq!(error, BridgeError::ConfidenceOutOfRange);
    }

    #[test]
    fn non_nfc_surface_is_rejected() {
        // ALEF + COMBINING HAMZA ABOVE normalizes to U+0623 ARABIC LETTER ALEF WITH HAMZA ABOVE.
        let input = observation(vec![candidate(
            "non-nfc",
            9_000,
            vec![grapheme(ArabicAbjadLetter::Alif, "ا\u{0654}", 0)],
        )]);
        let error = bridge_observation(&input).unwrap_err();
        assert_eq!(error, BridgeError::NonNfcText);
    }

    #[test]
    fn static_image_with_trajectory_is_rejected() {
        let mut g = grapheme(ArabicAbjadLetter::Alif, "ا", 0);
        g.trajectory_segment = Some("segment-1".to_owned());
        let mut input = observation(vec![candidate("image", 8_000, vec![g])]);
        input.source_modality = SourceModality::Image;
        let error = bridge_observation(&input).unwrap_err();
        assert_eq!(error, BridgeError::TrajectoryWithoutPenSource);
    }

    #[test]
    fn ambiguous_candidates_preserve_order() {
        let first = candidate(
            "first",
            3_000,
            vec![grapheme(ArabicAbjadLetter::Seen, "س", 0)],
        );
        let second = candidate(
            "second",
            9_000,
            vec![grapheme(ArabicAbjadLetter::Sad, "ص", 0)],
        );
        let output = bridge_observation(&observation(vec![first, second])).unwrap();
        assert!(output.ambiguity_preserved);
        assert_eq!(output.candidate_encodings.len(), 2);
        assert_eq!(output.candidate_encodings[0].candidate_id, "first");
        assert_eq!(output.candidate_encodings[1].candidate_id, "second");
    }

    #[test]
    fn tariq_bridge_matches_gate_215() {
        let output = bridge_observation(&observation(vec![tariq_candidate("tariq")])).unwrap();
        let encoded = &output.candidate_encodings[0];
        assert_eq!(encoded.derived_abjad_values, vec![9, 1, 200, 100]);
        assert_eq!(encoded.abjad_sum, 310);
        assert_eq!(encoded.abjad_product, 180_000);
        assert_eq!(encoded.name_node, 10);
        assert_eq!(encoded.routing_path.first().copied(), Some(9));
        assert_eq!(encoded.routing_path.last().copied(), Some(4));
    }

    #[test]
    fn not_visible_dot_evidence_is_preserved() {
        let mut g = grapheme(ArabicAbjadLetter::Alif, "ا", 0);
        g.dot_evidence = DotEvidence::NotVisible;
        let output = bridge_observation(&observation(vec![candidate("dots", 7_000, vec![g])])).unwrap();
        assert_eq!(output.candidate_encodings[0].graphemes[0].dot_count, 0);
        assert_eq!(output.candidate_encodings[0].graphemes[0].dot_evidence, DotEvidence::NotVisible);
    }

    #[test]
    fn identical_input_produces_identical_output() {
        let input = observation(vec![tariq_candidate("stable")]);
        let first = bridge_observation(&input).unwrap();
        let second = bridge_observation(&input).unwrap();
        assert_eq!(first, second);
    }

    #[test]
    fn output_discriminators_are_evidence_only() {
        let output = bridge_observation(&observation(vec![tariq_candidate("tariq")])).unwrap();
        assert_eq!(output.record_kind, ABJAD_CAPABILITY_ENCODING_KIND);
        assert_eq!(output.schema_version, SCHEMA_VERSION);
        assert_eq!(output.derivation_kind, "DETERMINISTIC_FROM_UNTRUSTED_OBSERVATION");
        assert_eq!(output.epistemic_ceiling, "T2");
    }
}
