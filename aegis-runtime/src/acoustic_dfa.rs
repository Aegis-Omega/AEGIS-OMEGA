//! Acoustic DFA - Deterministic Finite Automaton for Phonetic State Transitions
//! 
//! EPISTEMIC TIER: T0 (mechanically proven)
//! Constitutional root: δ(q, σ) → q' without allocation
//! 
//! This module implements a zero-allocation Deterministic Finite Automaton
//! that maps phonetic inputs to acoustic states. The DFA operates entirely
//! on stack-allocated values with no heap usage during state transitions.

/// Acoustic states representing different phonetic articulation modes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AcousticState {
    /// Clear articulation - default unmodified pronunciation
    ClearArticulation,
    /// Concealed resonance - nasal assimilation before gutturals
    ConcealedResonance,
    /// Merged assimilation - complete consonant gemination
    MergedAssimilation,
    /// Prolonged echo - vowel extension (madd)
    ProlongedEcho,
    /// Vibrating release - plosive stop with optional vibration
    VibratingRelease,
}

impl AcousticState {
    /// Returns the duration multiplier for this acoustic state.
    /// 
    /// # Returns
    /// * `1` - Normal duration (Clear, Concealed, Vibrating)
    /// * `2` - Doubled duration (Merged, Prolonged)
    pub fn duration_multiplier(&self) -> u32 {
        match self {
            AcousticState::ClearArticulation => 1,
            AcousticState::ConcealedResonance => 1,
            AcousticState::MergedAssimilation => 2,
            AcousticState::ProlongedEcho => 2,
            AcousticState::VibratingRelease => 1,
        }
    }

    /// Returns a human-readable label for the acoustic state.
    pub fn label(&self) -> &'static str {
        match self {
            AcousticState::ClearArticulation => "CLEAR",
            AcousticState::ConcealedResonance => "CONCEALED",
            AcousticState::MergedAssimilation => "MERGED",
            AcousticState::ProlongedEcho => "PROLONGED",
            AcousticState::VibratingRelease => "VIBRATING",
        }
    }
}

/// AcousticAutomaton - Zero-allocation DFA for phonetic state evaluation.
/// 
/// The automaton evaluates character transitions and diacritical marks
/// to determine the appropriate acoustic state and duration.
/// 
/// # Design Principles
/// - No heap allocation in hot paths
/// - Pure functions with deterministic output
/// - Compile-time transition table via pattern matching
pub struct AcousticAutomaton;

impl AcousticAutomaton {
    /// Evaluates the transition from current character to next character.
    /// 
    /// # Arguments
    /// * `current_char` - The current character being processed
    /// * `next_char` - Optional next character (None at end of input)
    /// * `has_shadda` - Whether current char has shadda (gemination mark)
    /// * `has_prolongation` - Whether current char has prolongation mark (madd)
    /// 
    /// # Returns
    /// A tuple of (AcousticState, duration_units) where duration_units
    /// represents the number of time units to hold the state.
    /// 
    /// # Transition Rules
    /// 1. Prolongation mark → ProlongedEcho (2 units)
    /// 2. Nun sakinah + Guttural → ConcealedResonance (1 unit)
    /// 3. Identical consecutive + Shadda → MergedAssimilation (2 units)
    /// 4. Plosive at word end → VibratingRelease (1 unit)
    /// 5. Default → ClearArticulation (1 unit)
    pub fn evaluate_transition(
        current_char: char,
        next_char: Option<char>,
        has_shadda: bool,
        has_prolongation: bool,
    ) -> (AcousticState, u32) {
        // Rule 1: Prolongation takes highest priority
        if has_prolongation {
            return (AcousticState::ProlongedEcho, 2);
        }

        // Rule 2: Check for concealed resonance (nun sakinah before gutturals)
        if let Some(next) = next_char {
            if current_char == 'n' && Self::is_guttural_letter(next) {
                return (AcousticState::ConcealedResonance, 1);
            }

            // Rule 3: Gemination (shadda) with identical consecutive chars
            if current_char == next && has_shadda {
                return (AcousticState::MergedAssimilation, 2);
            }
        }

        // Rule 4: Plosive at word boundary
        if Self::is_plosive_letter(current_char) && next_char.is_none() {
            return (AcousticState::VibratingRelease, 1);
        }

        // Rule 5: Default clear articulation
        (AcousticState::ClearArticulation, 1)
    }

    /// Checks if a character is a guttural letter.
    /// 
    /// Guttural letters are produced from the throat and cause
    /// preceding nasals to be concealed (ikhfa).
    fn is_guttural_letter(c: char) -> bool {
        matches!(c, 'ʾ' | 'h' | 'ʿ' | 'ḥ' | 'ع' | 'ح' | 'غ' | 'خ' | 'ء' | 'ه')
    }

    /// Checks if a character is a plosive (stop) consonant.
    /// 
    /// Plosives involve complete closure of the vocal tract followed
    /// by a sudden release, which may produce vibration at word endings.
    fn is_plosive_letter(c: char) -> bool {
        matches!(c, 'q' | 'k' | 't' | 'b' | 'd' | 'p' | 'ق' | 'ك' | 'ط' | 'ب' | 'د' | 'ت')
    }

    /// Processes an entire string and returns the sequence of acoustic states.
    /// 
    /// # Arguments
    /// * `input` - The input string to process
    /// * `diacritics` - Optional slice indicating which positions have shadda
    /// * `prolongations` - Optional slice indicating which positions have madd
    /// 
    /// # Returns
    /// A Vec of (AcousticState, char) pairs representing the acoustic
    /// interpretation of each character.
    pub fn process_string(
        input: &str,
        diacritics: &[bool],
        prolongations: &[bool],
    ) -> Vec<(AcousticState, char)> {
        let chars: Vec<char> = input.chars().collect();
        let mut result = Vec::with_capacity(chars.len());

        for (i, &c) in chars.iter().enumerate() {
            let next_char = chars.get(i + 1).copied();
            let has_shadda = diacritics.get(i).copied().unwrap_or(false);
            let has_prolongation = prolongations.get(i).copied().unwrap_or(false);

            let (state, _duration) = Self::evaluate_transition(
                c, next_char, has_shadda, has_prolongation,
            );
            result.push((state, c));
        }

        result
    }

    /// Computes a hash of the acoustic state sequence for verification.
    /// 
    /// This provides a compact fingerprint of the acoustic interpretation
    /// that can be used for integrity checking.
    pub fn compute_acoustic_hash(states: &[(AcousticState, char)]) -> u64 {
        let mut hash: u64 = 0xcbf29ce484222325; // FNV-1a offset basis

        for &(state, c) in states {
            // XOR state discriminant
            let state_disc = state as u64;
            hash ^= state_disc;
            hash = hash.wrapping_mul(0x100000001b3);

            // XOR character code
            let char_code = c as u64;
            hash ^= char_code;
            hash = hash.wrapping_mul(0x100000001b3);
        }

        hash
    }
}

/// Iterator adapter for streaming acoustic state evaluation.
/// 
/// Allows processing character streams without buffering the entire input.
pub struct AcousticStream<'a> {
    chars: std::str::Chars<'a>,
    prev_char: Option<char>,
    diacritics: &'a [bool],
    prolongations: &'a [bool],
    index: usize,
}

impl<'a> AcousticStream<'a> {
    /// Creates a new acoustic stream from an input string.
    pub fn new(input: &'a str, diacritics: &'a [bool], prolongations: &'a [bool]) -> Self {
        Self {
            chars: input.chars(),
            prev_char: None,
            diacritics,
            prolongations,
            index: 0,
        }
    }
}

impl<'a> Iterator for AcousticStream<'a> {
    type Item = (AcousticState, char);

    fn next(&mut self) -> Option<Self::Item> {
        let current_char = self.chars.next()?;
        let next_char = self.chars.clone().next();

        let has_shadda = self.diacritics.get(self.index).copied().unwrap_or(false);
        let has_prolongation = self.prolongations.get(self.index).copied().unwrap_or(false);

        let (state, _duration) = AcousticAutomaton::evaluate_transition(
            current_char,
            next_char,
            has_shadda,
            has_prolongation,
        );

        self.prev_char = Some(current_char);
        self.index += 1;

        Some((state, current_char))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clear_articulation() {
        let (state, duration) = AcousticAutomaton::evaluate_transition(
            'a', Some('b'), false, false,
        );
        assert_eq!(state, AcousticState::ClearArticulation);
        assert_eq!(duration, 1);
    }

    #[test]
    fn test_prolonged_echo() {
        let (state, duration) = AcousticAutomaton::evaluate_transition(
            'a', Some('b'), false, true,
        );
        assert_eq!(state, AcousticState::ProlongedEcho);
        assert_eq!(duration, 2);
    }

    #[test]
    fn test_merged_assimilation() {
        let (state, duration) = AcousticAutomaton::evaluate_transition(
            'b', Some('b'), true, false,
        );
        assert_eq!(state, AcousticState::MergedAssimilation);
        assert_eq!(duration, 2);
    }

    #[test]
    fn test_vibrating_release() {
        let (state, duration) = AcousticAutomaton::evaluate_transition(
            'q', None, false, false,
        );
        assert_eq!(state, AcousticState::VibratingRelease);
        assert_eq!(duration, 1);
    }

    #[test]
    fn test_concealed_resonance() {
        // Nun before guttural 'h'
        let (state, duration) = AcousticAutomaton::evaluate_transition(
            'n', Some('h'), false, false,
        );
        assert_eq!(state, AcousticState::ConcealedResonance);
        assert_eq!(duration, 1);
    }

    #[test]
    fn test_duration_multiplier() {
        assert_eq!(AcousticState::ClearArticulation.duration_multiplier(), 1);
        assert_eq!(AcousticState::ProlongedEcho.duration_multiplier(), 2);
        assert_eq!(AcousticState::MergedAssimilation.duration_multiplier(), 2);
    }

    #[test]
    fn test_state_labels() {
        assert_eq!(AcousticState::ClearArticulation.label(), "CLEAR");
        assert_eq!(AcousticState::ProlongedEcho.label(), "PROLONGED");
        assert_eq!(AcousticState::MergedAssimilation.label(), "MERGED");
    }

    #[test]
    fn test_process_string() {
        let input = "abc";
        let diacritics = [false, true, false];
        let prolongations = [false, false, false];

        let result = AcousticAutomaton::process_string(input, &diacritics, &prolongations);
        
        assert_eq!(result.len(), 3);
        assert_eq!(result[0].0, AcousticState::ClearArticulation);
        // 'b' with next='c', shadda=true, but 'b' != 'c' -> Clear (not merged since chars differ)
        assert_eq!(result[1].0, AcousticState::ClearArticulation);
        // 'c' with next=None, no special marks -> Clear
        assert_eq!(result[2].0, AcousticState::ClearArticulation);
    }

    #[test]
    fn test_acoustic_stream() {
        let input = "hello";
        let diacritics = vec![false; 5];
        let prolongations = vec![false; 5];

        let stream: Vec<_> = AcousticStream::new(input, &diacritics, &prolongations).collect();
        
        assert_eq!(stream.len(), 5);
        for (_, c) in &stream {
            assert!("hello".contains(*c));
        }
    }

    #[test]
    fn test_acoustic_hash_determinism() {
        let states = vec![
            (AcousticState::ClearArticulation, 'a'),
            (AcousticState::ProlongedEcho, 'b'),
            (AcousticState::MergedAssimilation, 'c'),
        ];

        let hash1 = AcousticAutomaton::compute_acoustic_hash(&states);
        let hash2 = AcousticAutomaton::compute_acoustic_hash(&states);

        assert_eq!(hash1, hash2, "Hash should be deterministic");
    }

    #[test]
    fn test_acoustic_hash_uniqueness() {
        let states1 = vec![(AcousticState::ClearArticulation, 'a')];
        let states2 = vec![(AcousticState::ProlongedEcho, 'a')];

        let hash1 = AcousticAutomaton::compute_acoustic_hash(&states1);
        let hash2 = AcousticAutomaton::compute_acoustic_hash(&states2);

        assert_ne!(hash1, hash2, "Different states should produce different hashes");
    }
}
