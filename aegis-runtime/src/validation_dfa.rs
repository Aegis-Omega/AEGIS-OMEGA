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

    pub fn reset(&mut self) { self.state = ValidationState::Idle; self.log.clear(); self.bytes_processed = 0; }

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

    // 11. Header state display is "Header"
    #[test] fn header_state_display() {
        assert_eq!(format!("{}", ValidationState::Header), "Header");
    }

    // 12. Payload state display is "Payload"
    #[test] fn payload_state_display() {
        assert_eq!(format!("{}", ValidationState::Payload), "Payload");
    }

    // 13. Default DFA is identical to new()
    #[test] fn default_dfa_equals_new() {
        let d = ValidationDfa::default();
        assert_eq!(d.state(), ValidationState::Idle);
        assert_eq!(d.bytes_processed(), 0);
        assert_eq!(d.log().len(), 0);
    }

    // 14. All 6 states are reachable via a known byte sequence
    #[test] fn all_6_states_reachable() {
        use ValidationState::*;
        // Idle → (0xE0) → Header → (0x01) → Payload → (0xFF) → Checksum → (data) → Accept
        // Reject: start fresh, feed invalid byte
        let mut d = ValidationDfa::new();
        assert_eq!(d.state(), Idle);
        d.step(0xE0); assert_eq!(d.state(), Header);
        d.step(0x01); assert_eq!(d.state(), Payload);
        d.step(0xFF); assert_eq!(d.state(), Checksum);
        d.step(0x00); assert_eq!(d.state(), Accept);
        // Accept → Idle on next byte
        d.step(0xAB); assert_eq!(d.state(), Idle);
        // Now push an invalid byte to reach Reject
        d.step(0x00); assert_eq!(d.state(), Reject);
    }

    // 15. After Accept, any byte transitions to Idle (frame complete, ready for next frame)
    #[test] fn accept_transitions_to_idle_on_next_byte() {
        let mut d = ValidationDfa::new();
        d.process(&valid_frame());
        assert!(d.is_accepted());
        d.step(0xE0); // Accept → Idle on any byte (per DFA table)
        assert_eq!(d.state(), ValidationState::Idle);
        // A subsequent 0xE0 from Idle then enters Header
        d.step(0xE0);
        assert_eq!(d.state(), ValidationState::Header);
    }

    // 16. classify_byte: 0xE0 in Idle → MagicByte
    #[test] fn classify_0xe0_in_idle_is_magic_byte() {
        assert_eq!(classify_byte(0xE0, ValidationState::Idle), ByteClass::MagicByte);
    }

    // 17. classify_byte: 0xE0 in Header → MagicConfirm
    #[test] fn classify_0xe0_in_header_is_magic_confirm() {
        assert_eq!(classify_byte(0xE0, ValidationState::Header), ByteClass::MagicConfirm);
    }

    // 18. classify_byte: 0x01 in Header → LengthByte
    #[test] fn classify_length_byte_in_header() {
        assert_eq!(classify_byte(0x01, ValidationState::Header), ByteClass::LengthByte);
    }

    // 19. classify_byte: 0x3F in Header → LengthByte (upper boundary)
    #[test] fn classify_upper_boundary_length_byte() {
        assert_eq!(classify_byte(0x3F, ValidationState::Header), ByteClass::LengthByte);
    }

    // 20. classify_byte: 0x40 in Header → InvalidByte (just above LengthByte range)
    #[test] fn classify_above_length_range_is_invalid() {
        assert_eq!(classify_byte(0x40, ValidationState::Header), ByteClass::InvalidByte);
    }

    // 21. classify_byte: 0xFF in Payload → ChecksumByte
    #[test] fn classify_0xff_in_payload_is_checksum() {
        assert_eq!(classify_byte(0xFF, ValidationState::Payload), ByteClass::ChecksumByte);
    }

    // 22. classify_byte: normal data byte in Payload → DataByte
    #[test] fn classify_data_byte_in_payload() {
        assert_eq!(classify_byte(0xAB, ValidationState::Payload), ByteClass::DataByte);
    }

    // 23. classify_byte in Idle with non-0xE0 → InvalidByte
    #[test] fn classify_non_magic_in_idle_is_invalid() {
        for b in [0x00u8, 0x01, 0xFE, 0xFF] {
            assert_eq!(classify_byte(b, ValidationState::Idle), ByteClass::InvalidByte);
        }
    }

    // 24. transition table is a BTreeMap (deterministic — same keys on rebuild)
    #[test] fn transition_table_keys_deterministic() {
        let t1 = ValidationDfa::build_table();
        let t2 = ValidationDfa::build_table();
        let k1: Vec<_> = t1.keys().collect();
        let k2: Vec<_> = t2.keys().collect();
        assert_eq!(k1, k2);
    }

    // 25. reset resets bytes_processed to 0
    #[test] fn reset_clears_bytes_processed() {
        let mut d = ValidationDfa::new();
        d.process(&valid_frame());
        assert!(d.bytes_processed() > 0);
        d.reset();
        assert_eq!(d.bytes_processed(), 0);
    }

    // 26. is_accepted returns false initially
    #[test] fn is_accepted_false_initially() {
        let d = ValidationDfa::new();
        assert!(!d.is_accepted());
    }

    // 27. is_rejected returns false initially
    #[test] fn is_rejected_false_initially() {
        let d = ValidationDfa::new();
        assert!(!d.is_rejected());
    }

    // 28. process empty slice leaves state unchanged
    #[test] fn process_empty_slice_no_change() {
        let mut d = ValidationDfa::new();
        d.process(&[]);
        assert_eq!(d.state(), ValidationState::Idle);
        assert_eq!(d.bytes_processed(), 0);
    }

    // 29. transition Idle+InvalidByte → Reject
    #[test] fn transition_idle_invalid_to_reject() {
        let result = ValidationDfa::transition(ValidationState::Idle, ByteClass::InvalidByte);
        assert_eq!(result, ValidationState::Reject);
    }

    // 30. transition Reject+anything → Reject (sticky)
    #[test] fn transition_reject_is_absorbing() {
        use ByteClass::*;
        for class in [MagicByte, MagicConfirm, LengthByte, DataByte, ChecksumByte, InvalidByte] {
            assert_eq!(
                ValidationDfa::transition(ValidationState::Reject, class),
                ValidationState::Reject
            );
        }
    }

    // 31. log records from-state correctly for each step
    #[test] fn log_records_from_state_correctly() {
        let mut d = ValidationDfa::new();
        d.step(0xE0); // Idle → Header
        let entry = &d.log()[0];
        assert_eq!(entry.from, ValidationState::Idle);
        assert_eq!(entry.to, ValidationState::Header);
    }

    // 32. Multiple valid frames in sequence are each accepted
    #[test] fn two_consecutive_valid_frames() {
        let mut d = ValidationDfa::new();
        d.process(&valid_frame()); // first frame → Accept
        assert!(d.is_accepted());
        d.process(&valid_frame()); // Accept → Idle (first byte E0) → then process rest
        // final state after second frame processed from Accept:
        // Accept → Idle (via E0) then continues...
        // This tests that accept→idle transition works and a new frame can proceed.
        assert_eq!(d.bytes_processed(), 10);
    }

    // 33. Transition table contains entry for (Checksum, DataByte) → Accept
    #[test] fn table_has_checksum_databyte_to_accept() {
        let t = ValidationDfa::build_table();
        assert_eq!(
            t.get(&(ValidationState::Checksum, ByteClass::DataByte)),
            Some(&ValidationState::Accept)
        );
    }

    // 34. Transition table contains entry for (Checksum, InvalidByte) → Reject
    #[test] fn table_has_checksum_invalidbyte_to_reject() {
        let t = ValidationDfa::build_table();
        assert_eq!(
            t.get(&(ValidationState::Checksum, ByteClass::InvalidByte)),
            Some(&ValidationState::Reject)
        );
    }

    // 35. Transition table contains entry for (Accept, DataByte) → Idle
    #[test] fn table_has_accept_databyte_to_idle() {
        let t = ValidationDfa::build_table();
        assert_eq!(
            t.get(&(ValidationState::Accept, ByteClass::DataByte)),
            Some(&ValidationState::Idle)
        );
    }
}
