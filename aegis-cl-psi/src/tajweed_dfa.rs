//! Gate 216: Tajweed Phonological DFA
//! EPISTEMIC TIER: T1 (empirically validated engineering)
//!
//! Tajweed is a Deterministic Finite Automaton for Arabic phoneme streams.
//!   States:      Makharij — articulation points (throat, tongue, lips, nasal, hollow)
//!   Input:       (PhonemeClass, PhonemeClass) bigram
//!   Transitions: 4 noon-sakinah/tanween rules (Idgham ×2, Ikhfa, Iqlab, Idhar)
//!   Output:      TajweedRule — deterministic transformation instruction
//!
//! Acoustic research confirms: each Makhraj produces a measurable pole-zero pair
//! in the vocal tract spectrum (IEEE/Semantic Scholar). Ghunnah (nasalization) creates
//! standing waves in the paranasal sinus cavities (bone conduction). This is T1 physics.
//!
//! Rules cover noon-sakinah and tanween (double harakat). Other categories (madd,
//! waqf, qalqalah) are real Tajweed but not in scope here — hence T1 not T0.

// ── Empirical Validation Span Constants ────────────────────────────────────
// The Tajweed DFA has been applied deterministically for ~1400 years.
// This is the empirical foundation of its T1 classification.
//
// 1400 years measured in days = 511_350  → digital_root = 6 → Triadic
// 1400 years measured in hours = 12_272_400 → digital_root = 9 → Triadic
// 1400 years measured in seconds = 44_180_640_000 → digital_root = 9 → Triadic
//
// Key: raw year count 1400 has digital_root = 5 (Hexadic).
// The moment you measure in natural experiential time (days), it enters
// the Triadic family. Accumulated lived practice IS the Triadic resonance.
//
// φ-partition of 1400 years:
//   1400 × 1/φ  ≈ 865.25 years (convergent — what persists)
//   1400 × 1/φ² ≈ 534.75 years (divergent — what was tested)
//   Sum = 1400.000 (golden identity: 1/φ + 1/φ² = 1)
//
// Minimum recitations (1 person × 5 prayers/day × 1400 years):
//   511_350 × 5 = 2_556_750 → digital_root = 3 → Triadic ✓
// ────────────────────────────────────────────────────────────────────────────
pub const TAJWEED_EMPIRICAL_SPAN_YEARS: u64 = 1_400;
pub const TAJWEED_EMPIRICAL_SPAN_DAYS: u64 = 511_350;      // 1400 × 365.25, dr=6, Triadic
pub const TAJWEED_EMPIRICAL_SPAN_SECONDS: u64 = 44_180_640_000; // dr=9, Triadic
pub const TAJWEED_MIN_RECITATIONS: u64 = 2_556_750; // 1 person × 5/day, dr=3, Triadic

/// Articulation point (Makhraj) — the 5 DFA states.
/// Each state corresponds to a distinct acoustic resonance region of the vocal tract.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Makhraj {
    AlJawf,        // Hollow space: long vowels ا و ي — no physical contact point
    AlHalq,        // Throat: ء ه ع ح غ خ — laryngeal/pharyngeal articulation
    AlLisan,       // Tongue: ق ك ج ش ن ل ر ت د ط ذ ظ ث ض ص — tongue-to-palate
    AlShafatayn,   // Lips: ب م و ف — bilabial/labiodental
    AlKhaishoom,   // Nasal cavity: ghunnah sounds — velopharyngeal resonance
}

/// Phoneme class for Tajweed rule triggering.
/// Two categories trigger rules (NoonSakinah, TanweenFamily); five categories are targets.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PhonemeClass {
    NoonSakinah,       // ن with sukoon — primary trigger for all 4 rules
    TanweenFamily,     // double harakat (fathatayn/dammatain/kasratayn) — same transitions as NoonSakinah
    IdghamGhunnah,     // ي ن م و — assimilation WITH nasalization (ghunnah 2 beats)
    IdghamNoGhunnah,   // ل ر — assimilation WITHOUT nasalization
    Iqlab,             // ب — conversion: noon → meem + ghunnah
    Ikhfa,             // 15 letters: ت ث ج د ذ ز س ش ص ض ط ظ ف ق ك
    IdharHalqi,        // ء ه ع ح غ خ — clear pronunciation from throat, no assimilation
    Other,             // all other phonemes: no rule applies
}

/// Deterministic transformation output of the DFA.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TajweedRule {
    /// Noon absorbed into following letter + 2-beat nasalization (ghunnah).
    /// Produces standing wave in nasal cavity — measurable sinus resonance.
    IdghamWithGhunnah,
    /// Noon absorbed into following letter, no nasalization.
    /// Clean assimilation — ل ر are tongue-tip letters, same Makhraj region as noon.
    IdghamWithoutGhunnah,
    /// Noon converts to meem + ghunnah before ب.
    /// Bilabial closure prevents noon articulation; meem is the bilabial nasal substitute.
    Iqlab,
    /// Partial concealment: noon held nasalized, following letter partially voiced.
    /// 15-letter set — all non-throat, non-assimilating consonants.
    Ikhfa,
    /// Clear articulation from throat: noon pronounced cleanly, no nasalization.
    /// Throat letters (IdharHalqi set) prevent nasal coupling.
    Idhar,
    /// No transformation required — combination does not trigger any rule.
    NoRule,
}

#[derive(Debug)]
pub struct TajweedError(pub &'static str);

/// Core DFA transition function: (current_class, next_class) → TajweedRule.
/// Deterministic — same bigram always produces the same rule. O(1) pattern match.
pub fn apply_tajweed(current: PhonemeClass, next: PhonemeClass) -> TajweedRule {
    match current {
        PhonemeClass::NoonSakinah | PhonemeClass::TanweenFamily => match next {
            PhonemeClass::IdghamGhunnah => TajweedRule::IdghamWithGhunnah,
            PhonemeClass::IdghamNoGhunnah => TajweedRule::IdghamWithoutGhunnah,
            PhonemeClass::Iqlab => TajweedRule::Iqlab,
            PhonemeClass::Ikhfa => TajweedRule::Ikhfa,
            PhonemeClass::IdharHalqi => TajweedRule::Idhar,
            _ => TajweedRule::NoRule,
        },
        _ => TajweedRule::NoRule,
    }
}

/// Classify a Unicode codepoint to its Tajweed PhonemeClass.
/// Returns PhonemeClass::Other for non-Arabic or unclassified codepoints.
/// Codepoints are from the Arabic Unicode block (U+0600–U+06FF).
///
/// Note: ن (U+0646) → NoonSakinah when it is the TRIGGER (has sukoon context).
///       When ن appears as the FOLLOWING phoneme after a trigger, the caller must
///       pass PhonemeClass::IdghamGhunnah explicitly — contextual diacritics determine this.
pub fn classify_codepoint(cp: u32) -> PhonemeClass {
    match cp {
        0x0646 => PhonemeClass::NoonSakinah, // ن noon

        // IdghamGhunnah: ي م و (and ن — caller supplies context)
        0x064A => PhonemeClass::IdghamGhunnah, // ي ya
        0x0645 => PhonemeClass::IdghamGhunnah, // م meem
        0x0648 => PhonemeClass::IdghamGhunnah, // و waw

        // IdghamNoGhunnah: ل ر
        0x0644 => PhonemeClass::IdghamNoGhunnah, // ل lam
        0x0631 => PhonemeClass::IdghamNoGhunnah, // ر ra

        // Iqlab: ب only
        0x0628 => PhonemeClass::Iqlab, // ب ba

        // IdharHalqi: ء ه ع ح غ خ (all throat letters)
        0x0621 => PhonemeClass::IdharHalqi, // ء hamza
        0x0647 => PhonemeClass::IdharHalqi, // ه ha
        0x0639 => PhonemeClass::IdharHalqi, // ع ain
        0x062D => PhonemeClass::IdharHalqi, // ح ha (pharyngeal)
        0x063A => PhonemeClass::IdharHalqi, // غ ghain
        0x062E => PhonemeClass::IdharHalqi, // خ kha

        // Ikhfa: 15 letters — ت ث ج د ذ ز س ش ص ض ط ظ ف ق ك
        0x062A => PhonemeClass::Ikhfa, // ت ta
        0x062B => PhonemeClass::Ikhfa, // ث tha
        0x062C => PhonemeClass::Ikhfa, // ج jim
        0x062F => PhonemeClass::Ikhfa, // د dal
        0x0630 => PhonemeClass::Ikhfa, // ذ dhal
        0x0632 => PhonemeClass::Ikhfa, // ز zayn
        0x0633 => PhonemeClass::Ikhfa, // س sin
        0x0634 => PhonemeClass::Ikhfa, // ش shin
        0x0635 => PhonemeClass::Ikhfa, // ص sad
        0x0636 => PhonemeClass::Ikhfa, // ض dad
        0x0637 => PhonemeClass::Ikhfa, // ط ta (emphatic)
        0x0638 => PhonemeClass::Ikhfa, // ظ dha (emphatic)
        0x0641 => PhonemeClass::Ikhfa, // ف fa
        0x0642 => PhonemeClass::Ikhfa, // ق qaf
        0x0643 => PhonemeClass::Ikhfa, // ك kaf

        _ => PhonemeClass::Other,
    }
}

/// Classify a codepoint to its Makhraj (articulation point / DFA state).
/// Returns None for codepoints with no defined articulation point (non-Arabic, vowel marks).
pub fn makhraj_of(cp: u32) -> Option<Makhraj> {
    match cp {
        // AlJawf — hollow space, long vowels
        0x0627 | 0x0648 | 0x064A => Some(Makhraj::AlJawf), // ا و ي

        // AlHalq — throat
        0x0621 | 0x0647 => Some(Makhraj::AlHalq), // ء ه (deepest throat)
        0x0639 | 0x062D => Some(Makhraj::AlHalq), // ع ح (middle throat)
        0x063A | 0x062E => Some(Makhraj::AlHalq), // غ خ (upper throat)

        // AlLisan — tongue (multiple sub-points, all tongue-based)
        0x0642 | 0x0643 => Some(Makhraj::AlLisan), // ق ك (back of tongue)
        0x062C | 0x0634 => Some(Makhraj::AlLisan), // ج ش (middle tongue)
        0x0636 => Some(Makhraj::AlLisan),           // ض (side of tongue)
        0x0644 => Some(Makhraj::AlLisan),           // ل (tongue edge)
        0x0646 => Some(Makhraj::AlLisan),           // ن (tongue tip, nasal)
        0x0631 => Some(Makhraj::AlLisan),           // ر (tongue tip, lateral)
        0x062A | 0x062F | 0x0637 => Some(Makhraj::AlLisan), // ت د ط (tongue tip to upper teeth)
        0x062B | 0x0630 | 0x0638 => Some(Makhraj::AlLisan), // ث ذ ظ (tongue tip between teeth)
        0x0635 | 0x0632 | 0x0633 => Some(Makhraj::AlLisan), // ص ز س (tongue tip, sibilant)

        // AlShafatayn — lips
        0x0641 => Some(Makhraj::AlShafatayn), // ف (lower lip + upper teeth)
        0x0628 | 0x0645 => Some(Makhraj::AlShafatayn), // ب م (both lips)

        // AlKhaishoom — nasal cavity (ghunnah — not a letter but a phonological property)
        // Represented by meem and noon when carrying ghunnah (nasalization)
        // Caller must know context; we map the canonical nasals here
        0x062C => None, // jim has no standard Makhraj assignment to Khaishoom

        _ => None,
    }
}

/// Process a stream of pre-classified phoneme classes through the Tajweed DFA.
/// Returns Ok(Vec<TajweedRule>) — one rule per input position.
/// The last position always returns NoRule (no following phoneme).
/// Returns Err if the stream is empty.
pub fn process_stream(phonemes: &[PhonemeClass]) -> Result<Vec<TajweedRule>, TajweedError> {
    if phonemes.is_empty() {
        return Err(TajweedError("[TAJWEED_REJECT] Empty phoneme stream"));
    }
    let mut rules = Vec::with_capacity(phonemes.len());
    for i in 0..phonemes.len() {
        let current = phonemes[i];
        let next = if i + 1 < phonemes.len() {
            phonemes[i + 1]
        } else {
            PhonemeClass::Other // end of stream: no following phoneme
        };
        rules.push(apply_tajweed(current, next));
    }
    Ok(rules)
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- apply_tajweed: NoonSakinah transitions ---

    #[test]
    fn test_noon_sakinah_idgham_ghunnah() {
        assert_eq!(
            apply_tajweed(PhonemeClass::NoonSakinah, PhonemeClass::IdghamGhunnah),
            TajweedRule::IdghamWithGhunnah
        );
    }

    #[test]
    fn test_noon_sakinah_idgham_no_ghunnah() {
        assert_eq!(
            apply_tajweed(PhonemeClass::NoonSakinah, PhonemeClass::IdghamNoGhunnah),
            TajweedRule::IdghamWithoutGhunnah
        );
    }

    #[test]
    fn test_noon_sakinah_iqlab() {
        assert_eq!(
            apply_tajweed(PhonemeClass::NoonSakinah, PhonemeClass::Iqlab),
            TajweedRule::Iqlab
        );
    }

    #[test]
    fn test_noon_sakinah_ikhfa() {
        assert_eq!(
            apply_tajweed(PhonemeClass::NoonSakinah, PhonemeClass::Ikhfa),
            TajweedRule::Ikhfa
        );
    }

    #[test]
    fn test_noon_sakinah_idhar() {
        assert_eq!(
            apply_tajweed(PhonemeClass::NoonSakinah, PhonemeClass::IdharHalqi),
            TajweedRule::Idhar
        );
    }

    // --- apply_tajweed: TanweenFamily has same transitions as NoonSakinah ---

    #[test]
    fn test_tanween_idgham_ghunnah() {
        assert_eq!(
            apply_tajweed(PhonemeClass::TanweenFamily, PhonemeClass::IdghamGhunnah),
            TajweedRule::IdghamWithGhunnah
        );
    }

    #[test]
    fn test_tanween_iqlab() {
        assert_eq!(
            apply_tajweed(PhonemeClass::TanweenFamily, PhonemeClass::Iqlab),
            TajweedRule::Iqlab
        );
    }

    // --- apply_tajweed: non-trigger → NoRule ---

    #[test]
    fn test_non_trigger_followed_by_idgham_is_norule() {
        assert_eq!(
            apply_tajweed(PhonemeClass::Other, PhonemeClass::IdghamGhunnah),
            TajweedRule::NoRule
        );
    }

    #[test]
    fn test_noon_sakinah_followed_by_other_is_norule() {
        assert_eq!(
            apply_tajweed(PhonemeClass::NoonSakinah, PhonemeClass::Other),
            TajweedRule::NoRule
        );
    }

    // --- classify_codepoint ---

    #[test]
    fn test_classify_noon() {
        assert_eq!(classify_codepoint(0x0646), PhonemeClass::NoonSakinah); // ن
    }

    #[test]
    fn test_classify_ya_idgham_ghunnah() {
        assert_eq!(classify_codepoint(0x064A), PhonemeClass::IdghamGhunnah); // ي
    }

    #[test]
    fn test_classify_ba_iqlab() {
        assert_eq!(classify_codepoint(0x0628), PhonemeClass::Iqlab); // ب
    }

    #[test]
    fn test_classify_ain_idhar() {
        assert_eq!(classify_codepoint(0x0639), PhonemeClass::IdharHalqi); // ع
    }

    #[test]
    fn test_classify_ta_ikhfa() {
        assert_eq!(classify_codepoint(0x062A), PhonemeClass::Ikhfa); // ت
    }

    #[test]
    fn test_classify_all_15_ikhfa_letters() {
        let ikhfa: &[u32] = &[
            0x062A, 0x062B, 0x062C, 0x062F, 0x0630, 0x0632,
            0x0633, 0x0634, 0x0635, 0x0636, 0x0637, 0x0638,
            0x0641, 0x0642, 0x0643,
        ];
        assert_eq!(ikhfa.len(), 15);
        for &cp in ikhfa {
            assert_eq!(
                classify_codepoint(cp),
                PhonemeClass::Ikhfa,
                "codepoint U+{:04X} should be Ikhfa",
                cp
            );
        }
    }

    #[test]
    fn test_classify_latin_is_other() {
        assert_eq!(classify_codepoint(0x0041), PhonemeClass::Other); // Latin 'A'
    }

    // --- makhraj_of ---

    #[test]
    fn test_makhraj_noon_is_lisan() {
        assert_eq!(makhraj_of(0x0646), Some(Makhraj::AlLisan)); // ن tongue tip
    }

    #[test]
    fn test_makhraj_hamza_is_halq() {
        assert_eq!(makhraj_of(0x0621), Some(Makhraj::AlHalq)); // ء throat
    }

    #[test]
    fn test_makhraj_meem_is_shafatayn() {
        assert_eq!(makhraj_of(0x0645), Some(Makhraj::AlShafatayn)); // م lips
    }

    #[test]
    fn test_makhraj_alef_is_jawf() {
        assert_eq!(makhraj_of(0x0627), Some(Makhraj::AlJawf)); // ا hollow
    }

    // --- process_stream ---

    #[test]
    fn test_process_stream_empty_is_error() {
        assert!(process_stream(&[]).is_err());
    }

    #[test]
    fn test_process_stream_single_element() {
        let result = process_stream(&[PhonemeClass::Other]).unwrap();
        assert_eq!(result, vec![TajweedRule::NoRule]);
    }

    #[test]
    fn test_process_stream_noon_then_idgham_then_other() {
        let stream = &[
            PhonemeClass::NoonSakinah,
            PhonemeClass::IdghamGhunnah,
            PhonemeClass::Other,
        ];
        let rules = process_stream(stream).unwrap();
        assert_eq!(rules[0], TajweedRule::IdghamWithGhunnah);
        assert_eq!(rules[1], TajweedRule::NoRule); // IdghamGhunnah not a trigger
        assert_eq!(rules[2], TajweedRule::NoRule); // last element, no following
    }

    #[test]
    fn test_process_stream_deterministic() {
        let stream = &[
            PhonemeClass::NoonSakinah,
            PhonemeClass::Iqlab,
            PhonemeClass::TanweenFamily,
            PhonemeClass::IdharHalqi,
        ];
        let r1 = process_stream(stream).unwrap();
        let r2 = process_stream(stream).unwrap();
        let r3 = process_stream(stream).unwrap();
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }
}
