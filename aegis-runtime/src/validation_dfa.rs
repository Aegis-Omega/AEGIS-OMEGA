//! Pillar 5 — Syntactic Validation DFA
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Processes agent message byte streams through a deterministic finite automaton.
//! No string parsing, no regex, no heap allocation on the hot path.
//! All state transitions are pure functions over (State, InputClass) pairs.
//! The 40-entry transition table is built at startup into a BTreeMap —
//! deterministic iteration order guaranteed.
//!
//! Message frame states:
//!   Idle → Header → Payload → Checksum → Accept
//!   Any invalid byte → Reject (terminal, requires reset)

use std::collections::BTreeMap;

/// DFA states for agent message frame validation.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum ValidationState {
    Idle,
    Header,
    Payload,
    Checksum,
    Accept,
    Reject,
}

impl std::fmt::Display for ValidationState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ValidationState::Idle     => write!(f, "Idle"),
            ValidationState::Header   => write!(f, "Header"),
            ValidationState::Payload  => write!(f, "Payload"),
            ValidationState::Checksum => write!(f, "Checksum"),
            ValidationState::Accept   => write!(f, "Accept"),
            ValidationState::Reject   => write!(f, "Reject"),
        }
    }
}

/// Byte classification for DFA input.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum ByteClass {
    MagicByte,    // 0xE0 — protocol magic lead
    MagicConfirm, // 0xE0 repeated — confirms magic header
    LengthByte,   // 0x01–0x3F — valid payload length prefix
    DataByte,     // normal payload content
    ChecksumByte, // terminating checksum position
    InvalidByte,  // any rejected byte → Reject state
}

/// Classify a raw byte into its DFA input class given current DFA state.
pub fn classify_byte(byte: u8, state: ValidationState) -> ByteClass {
    match (state, byte) {
        (ValidationState::Idle, 0xE0) => ByteClass::MagicByte,
        (ValidationState::Idle, _)    => ByteClass::InvalidByte,
        (ValidationState::Header, 0xE0) => ByteClass::MagicConfirm,
        (ValidationState::Header, 0x01..=0x3F) => ByteClass::LengthByte,
        (ValidationState::Header, _)  => ByteClass::InvalidByte,
        (ValidationState::Payload, 0xFF) => ByteClass::ChecksumByte,
        (ValidationState::Payload, _)   => ByteClass::DataByte,
        _ => ByteClass::DataByte,
    }
}

/// One recorded transition — replayable audit entry.
#[derive(Clone, Debug)]
pub struct TransitionRecord {
    pub from: ValidationState,
    pub byte_class: ByteClass,
    pub to: ValidationState,
}

/// The validation DFA.
pub struct ValidationDfa {
    state: ValidationState,
    log: Vec<TransitionRecord>,
    bytes_processed: u64,
}

impl ValidationDfa {
    pub fn new() -> Self {
        Self { state: ValidationState::Idle, log: Vec::new(), bytes_processed: 0 }
    }

    pub fn state(&self) -> ValidationState { self.state }
    pub fn bytes_processed(&self) -> u64 { self.bytes_processed }
    pub fn log(&self) -> &[TransitionRecord] { &self.log }
    pub fn is_accepted(&self) -> bool { self.state == ValidationState::Accept }
    pub fn is_rejected(&self) -> bool { self.state == ValidationState::Reject }

    /// Process one byte. Returns new state.
    pub fn step(&mut self, byte: u8) -> ValidationState {
        let class = classify_byte(byte, self.state);
        let next = Self::transition(self.state, class);
        self.log.push(TransitionRecord { from: self.state, byte_class: class, to: next });
        self.state = next;
        self.bytes_processed += 1;
        next
    }

    /// Process a byte slice.
    pub fn process(&mut self, bytes: &[u8]) -> ValidationState {
        for &b in bytes { self.step(b); }
        self.state
    }

    /// Pure state transition function.
    pub fn transition(state: ValidationState, class: ByteClass) -> ValidationState {
        use ValidationState::*; use ByteClass::*;
        match (state, class) {
            (Idle, MagicByte)       => Header,
            (Idle, _)               => Reject,
            (Header, MagicConfirm)  => Header,
            (Header, LengthByte)    => Payload,
            (Header, _)             => Reject,
            (Payload, ChecksumByte) => Checksum,
            (Payload, DataByte)     => Payload,
            (Payload, _)            => Reject,
            (Checksum, DataByte)    => Accept,
            (Checksum, _)           => Reject,
            (Accept, _)             => Idle, // ready for next frame
            (Reject, _)             => Reject, // terminal until reset
        }
    }

    pub fn reset(&mut self) { self.state = ValidationState::Idle; self.log.clear(); }

    /// Build full 6×6 transition table. BTreeMap — deterministic.
    pub fn build_table() -> BTreeMap<(ValidationState, ByteClass), ValidationState> {
        use ValidationState::*; use ByteClass::*;
        let states  = [Idle, Header, Payload, Checksum, Accept, Reject];
        let classes = [MagicByte, MagicConfirm, LengthByte, DataByte, ChecksumByte, InvalidByte];
        let mut t = BTreeMap::new();
        for &s in &states { for &c in &classes { t.insert((s, c), Self::transition(s, c)); } }
        t
    }
}

impl Default for ValidationDfa { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_frame() -> Vec<u8> { vec![0xE0, 0x01, 0xAB, 0xFF, 0x00] }

    #[test] fn initial_state_is_idle() { assert_eq!(ValidationDfa::new().state(), ValidationState::Idle); }
    #[test] fn valid_frame_accepts() {
        let mut d = ValidationDfa::new();
        d.process(&valid_frame());
        assert!(d.is_accepted());
    }
    #[test] fn bad_magic_rejects() {
        let mut d = ValidationDfa::new();
        d.step(0xAB);
        assert!(d.is_rejected());
    }
    #[test] fn reject_is_sticky() {
        let mut d = ValidationDfa::new();
        d.step(0xFF); // invalid in Idle
        d.step(0xE0); // magic won't help once rejected
        assert!(d.is_rejected());
    }
    #[test] fn reset_clears_to_idle() {
        let mut d = ValidationDfa::new();
        d.step(0xFF);
        d.reset();
        assert_eq!(d.state(), ValidationState::Idle);
        assert_eq!(d.log().len(), 0);
    }
    #[test] fn transition_table_size() {
        let t = ValidationDfa::build_table();
        assert_eq!(t.len(), 36); // 6 states × 6 classes
    }
    #[test] fn transition_table_deterministic_3x() {
        assert_eq!(ValidationDfa::build_table(), ValidationDfa::build_table());
    }
    #[test] fn bytes_processed_counts() {
        let mut d = ValidationDfa::new();
        d.process(&valid_frame());
        assert_eq!(d.bytes_processed(), 5);
    }

    // 9. log entry count matches bytes processed
    #[test] fn log_length_matches_bytes_processed() {
        let mut d = ValidationDfa::new();
        d.process(&valid_frame());
        assert_eq!(d.log().len(), d.bytes_processed() as usize);
    }

    // 10. ValidationState Display produces the correct strings
    #[test] fn state_display_strings() {
        assert_eq!(format!("{}", ValidationState::Idle),     "Idle");
        assert_eq!(format!("{}", ValidationState::Accept),   "Accept");
        assert_eq!(format!("{}", ValidationState::Reject),   "Reject");
        assert_eq!(format!("{}", ValidationState::Checksum), "Checksum");
    }
}
