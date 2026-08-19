//! Khatt–Abjad capability bridge v0.1.
//!
//! TDD RED phase: tests define the typed evidence boundary before implementation.

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
