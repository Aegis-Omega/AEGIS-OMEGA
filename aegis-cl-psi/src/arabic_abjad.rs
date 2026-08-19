//! Khatt–Abjad v0.1 — versioned Arabic Abjad convention.
//!
//! TDD RED phase: tests define the public mapping contract before implementation.

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seen_differs_between_systems() {
        assert_eq!(
            abjad_value(ArabicAbjadSystem::MashriqiV1, ArabicAbjadLetter::Seen),
            60
        );
        assert_eq!(
            abjad_value(ArabicAbjadSystem::MaghribiV1, ArabicAbjadLetter::Seen),
            300
        );
    }

    #[test]
    fn six_maghribi_overrides_are_exact() {
        let overrides = [
            (ArabicAbjadLetter::Sad, 90, 60),
            (ArabicAbjadLetter::Dad, 800, 90),
            (ArabicAbjadLetter::Seen, 60, 300),
            (ArabicAbjadLetter::Zah, 900, 800),
            (ArabicAbjadLetter::Ghayn, 1000, 900),
            (ArabicAbjadLetter::Sheen, 300, 1000),
        ];
        for (letter, mashriqi, maghribi) in overrides {
            assert_eq!(abjad_value(ArabicAbjadSystem::MashriqiV1, letter), mashriqi);
            assert_eq!(abjad_value(ArabicAbjadSystem::MaghribiV1, letter), maghribi);
        }
    }

    #[test]
    fn tariq_values_match_gate_215() {
        let values = [
            ArabicAbjadLetter::Tah,
            ArabicAbjadLetter::Alif,
            ArabicAbjadLetter::Ra,
            ArabicAbjadLetter::Qaf,
        ]
        .map(|letter| abjad_value(ArabicAbjadSystem::MashriqiV1, letter));
        assert_eq!(values, [9, 1, 200, 100]);
    }

    #[test]
    fn canonical_base_letters_serialize_as_arabic_glyphs() {
        assert_eq!(serde_json::to_string(&ArabicAbjadLetter::Alif).unwrap(), "\"ا\"");
        assert_eq!(serde_json::to_string(&ArabicAbjadLetter::Qaf).unwrap(), "\"ق\"");
        assert_eq!(serde_json::to_string(&ArabicAbjadLetter::Ghayn).unwrap(), "\"غ\"");
    }

    #[test]
    fn systems_serialize_with_explicit_version_names() {
        assert_eq!(serde_json::to_string(&ArabicAbjadSystem::MashriqiV1).unwrap(), "\"MASHRIQI_V1\"");
        assert_eq!(serde_json::to_string(&ArabicAbjadSystem::MaghribiV1).unwrap(), "\"MAGHRIBI_V1\"");
    }
}
