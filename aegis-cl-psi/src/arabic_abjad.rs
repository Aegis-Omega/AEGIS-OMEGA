//! Khatt–Abjad v0.1 — versioned Arabic Abjad convention.
//!
//! EPISTEMIC TIER: T2 (engineering representation).
//!
//! This module encodes a frozen historical letter→integer convention. It does not
//! claim that Abjad-derived arithmetic establishes linguistic truth, cognition,
//! authority, execution, or external effect.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ArabicAbjadSystem {
    MashriqiV1,
    MaghribiV1,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ArabicAbjadLetter {
    #[serde(rename = "ا")]
    Alif,
    #[serde(rename = "ب")]
    Ba,
    #[serde(rename = "ج")]
    Jim,
    #[serde(rename = "د")]
    Dal,
    #[serde(rename = "ه")]
    Ha,
    #[serde(rename = "و")]
    Waw,
    #[serde(rename = "ز")]
    Zay,
    #[serde(rename = "ح")]
    Hah,
    #[serde(rename = "ط")]
    Tah,
    #[serde(rename = "ي")]
    Ya,
    #[serde(rename = "ك")]
    Kaf,
    #[serde(rename = "ل")]
    Lam,
    #[serde(rename = "م")]
    Mim,
    #[serde(rename = "ن")]
    Nun,
    #[serde(rename = "س")]
    Seen,
    #[serde(rename = "ع")]
    Ayn,
    #[serde(rename = "ف")]
    Fa,
    #[serde(rename = "ص")]
    Sad,
    #[serde(rename = "ق")]
    Qaf,
    #[serde(rename = "ر")]
    Ra,
    #[serde(rename = "ش")]
    Sheen,
    #[serde(rename = "ت")]
    Ta,
    #[serde(rename = "ث")]
    Tha,
    #[serde(rename = "خ")]
    Kha,
    #[serde(rename = "ذ")]
    Dhal,
    #[serde(rename = "ض")]
    Dad,
    #[serde(rename = "ظ")]
    Zah,
    #[serde(rename = "غ")]
    Ghayn,
}

impl ArabicAbjadLetter {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Alif => "ا",
            Self::Ba => "ب",
            Self::Jim => "ج",
            Self::Dal => "د",
            Self::Ha => "ه",
            Self::Waw => "و",
            Self::Zay => "ز",
            Self::Hah => "ح",
            Self::Tah => "ط",
            Self::Ya => "ي",
            Self::Kaf => "ك",
            Self::Lam => "ل",
            Self::Mim => "م",
            Self::Nun => "ن",
            Self::Seen => "س",
            Self::Ayn => "ع",
            Self::Fa => "ف",
            Self::Sad => "ص",
            Self::Qaf => "ق",
            Self::Ra => "ر",
            Self::Sheen => "ش",
            Self::Ta => "ت",
            Self::Tha => "ث",
            Self::Kha => "خ",
            Self::Dhal => "ذ",
            Self::Dad => "ض",
            Self::Zah => "ظ",
            Self::Ghayn => "غ",
        }
    }
}

const fn mashriqi_value(letter: ArabicAbjadLetter) -> u64 {
    match letter {
        ArabicAbjadLetter::Alif => 1,
        ArabicAbjadLetter::Ba => 2,
        ArabicAbjadLetter::Jim => 3,
        ArabicAbjadLetter::Dal => 4,
        ArabicAbjadLetter::Ha => 5,
        ArabicAbjadLetter::Waw => 6,
        ArabicAbjadLetter::Zay => 7,
        ArabicAbjadLetter::Hah => 8,
        ArabicAbjadLetter::Tah => 9,
        ArabicAbjadLetter::Ya => 10,
        ArabicAbjadLetter::Kaf => 20,
        ArabicAbjadLetter::Lam => 30,
        ArabicAbjadLetter::Mim => 40,
        ArabicAbjadLetter::Nun => 50,
        ArabicAbjadLetter::Seen => 60,
        ArabicAbjadLetter::Ayn => 70,
        ArabicAbjadLetter::Fa => 80,
        ArabicAbjadLetter::Sad => 90,
        ArabicAbjadLetter::Qaf => 100,
        ArabicAbjadLetter::Ra => 200,
        ArabicAbjadLetter::Sheen => 300,
        ArabicAbjadLetter::Ta => 400,
        ArabicAbjadLetter::Tha => 500,
        ArabicAbjadLetter::Kha => 600,
        ArabicAbjadLetter::Dhal => 700,
        ArabicAbjadLetter::Dad => 800,
        ArabicAbjadLetter::Zah => 900,
        ArabicAbjadLetter::Ghayn => 1000,
    }
}

/// Return the integer value for one of the 28 supported base Arabic letters under
/// the explicitly selected v0.1 convention. There is intentionally no default system.
pub const fn abjad_value(system: ArabicAbjadSystem, letter: ArabicAbjadLetter) -> u64 {
    match system {
        ArabicAbjadSystem::MashriqiV1 => mashriqi_value(letter),
        ArabicAbjadSystem::MaghribiV1 => match letter {
            ArabicAbjadLetter::Sad => 60,
            ArabicAbjadLetter::Dad => 90,
            ArabicAbjadLetter::Seen => 300,
            ArabicAbjadLetter::Zah => 800,
            ArabicAbjadLetter::Ghayn => 900,
            ArabicAbjadLetter::Sheen => 1000,
            _ => mashriqi_value(letter),
        },
    }
}

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
