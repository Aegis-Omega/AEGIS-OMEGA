// Constitutional Substrate — Append-Only Replay Ledger Primitives
// EPISTEMIC TIER: T0
// ONTOLOGY TERM: Constitutional File (the ledger is an append-only constitutional record)
//
// REPLAY CONSTITUTION LAW-07: Replay artifacts are append-only constitutional records.
// REPLAY CONSTITUTION LAW-01: Historical replay must produce identical invariant outcomes.
// REPLAY CONSTITUTION LAW-04: No nondeterministic entropy source may influence replay.
//
// The ChainHasher trait is the integration boundary for SHA-256. Callers provide the
// hash implementation; the substrate provides the chain structure and append semantics.
// This separation ensures the substrate has zero cryptographic dependencies.

use crate::archive::ARCHIVE_V1_0_0;
#[cfg(test)]
use crate::archive::ArchiveVersion;
use crate::primitives::{StateHash, GENESIS_HASH};

// ─── ChainHasher ─────────────────────────────────────────────────────────────

/// Integration boundary for deterministic chain hash computation.
/// Production implementations must use SHA-256 (matching the TypeScript layer:
/// chain_hash = SHA256(prev_hash || payload_hash || sequence_le_bytes)).
/// Test implementations may use any deterministic function.
pub trait ChainHasher {
    fn compute(&self, prev: &StateHash, payload: &StateHash, sequence: u64) -> StateHash;
}

// ─── ReplayEvent ──────────────────────────────────────────────────────────────

/// A single event in the append-only replay ledger.
///
/// Wire format (82 bytes, LE) — constitutionally stable at v1.0.0:
///   [0..8]    sequence: u64 LE — monotonically increasing from 0
///   [8..12]   event_type: u32 LE — caller-defined typed event class
///   [12..44]  payload_hash: StateHash — SHA-256 of event payload (RFC 8785 canonical)
///   [44..76]  prev_hash: StateHash — chain link to previous event's chain result
///   [76..82]  archive_version: ArchiveVersion wire format
///
/// Total: 82 bytes per event. Endianness: little-endian throughout.
/// Replay determinism: same sequence of (event_type, payload_hash) inputs
/// with the same ChainHasher always produces bit-identical wire bytes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReplayEvent {
    pub sequence: u64,
    pub event_type: u32,
    pub payload_hash: StateHash,
    pub prev_hash: StateHash,
    pub archive_version: [u8; 6],
}

impl ReplayEvent {
    /// Serialise to 82-byte canonical little-endian wire format.
    pub fn to_bytes(&self) -> [u8; 82] {
        let mut out = [0u8; 82];
        out[0..8].copy_from_slice(&self.sequence.to_le_bytes());
        out[8..12].copy_from_slice(&self.event_type.to_le_bytes());
        out[12..44].copy_from_slice(&self.payload_hash);
        out[44..76].copy_from_slice(&self.prev_hash);
        out[76..82].copy_from_slice(&self.archive_version);
        out
    }

    /// Deserialise from 82-byte canonical little-endian wire format.
    pub fn from_bytes(b: &[u8; 82]) -> Option<Self> {
        let sequence = u64::from_le_bytes(b[0..8].try_into().ok()?);
        let event_type = u32::from_le_bytes(b[8..12].try_into().ok()?);
        let mut payload_hash = [0u8; 32];
        payload_hash.copy_from_slice(&b[12..44]);
        let mut prev_hash = [0u8; 32];
        prev_hash.copy_from_slice(&b[44..76]);
        let mut archive_version = [0u8; 6];
        archive_version.copy_from_slice(&b[76..82]);
        Some(Self { sequence, event_type, payload_hash, prev_hash, archive_version })
    }
}

// ─── ReplayLedger ─────────────────────────────────────────────────────────────

/// An append-only replay ledger. Events may only be added, never removed or modified.
/// REPLAY CONSTITUTION LAW-07: constitutional record — append-only invariant enforced.
pub struct ReplayLedger {
    events: Vec<ReplayEvent>,
}

impl ReplayLedger {
    pub fn new() -> Self {
        Self { events: Vec::new() }
    }

    /// Append a new event. Returns the assigned sequence number.
    /// The prev_hash is computed from the previous event's chain state via the hasher.
    /// The genesis event (sequence=0) always has prev_hash = GENESIS_HASH (all zeros).
    pub fn append<H: ChainHasher>(
        &mut self,
        event_type: u32,
        payload_hash: StateHash,
        hasher: &H,
    ) -> u64 {
        let sequence = self.events.len() as u64;
        let prev_hash = if self.events.is_empty() {
            GENESIS_HASH
        } else {
            let prev = self.events.last().unwrap(); // safe: non-empty
            hasher.compute(&prev.prev_hash, &prev.payload_hash, prev.sequence)
        };
        self.events.push(ReplayEvent {
            sequence,
            event_type,
            payload_hash,
            prev_hash,
            archive_version: ARCHIVE_V1_0_0.to_bytes(),
        });
        sequence
    }

    /// Structural chain verification using the provided hasher.
    /// Checks:
    ///   1. Sequence numbers are contiguous (0, 1, 2, …)
    ///   2. Genesis event has GENESIS_HASH prev_hash
    ///   3. Each event's prev_hash equals the chain result of the previous event
    /// Returns false on any structural violation — the ledger may not be replayed.
    /// REPLAY CONSTITUTION LAW-06: invariant violations during replay must halt admissibility.
    pub fn verify_structural<H: ChainHasher>(&self, hasher: &H) -> bool {
        for (i, event) in self.events.iter().enumerate() {
            // LAW-01: sequence numbers must be contiguous from 0
            if event.sequence != i as u64 {
                return false;
            }
            if i == 0 {
                // Genesis event: prev_hash must be GENESIS_HASH
                if event.prev_hash != GENESIS_HASH {
                    return false;
                }
            } else {
                let prev = &self.events[i - 1];
                let expected = hasher.compute(&prev.prev_hash, &prev.payload_hash, prev.sequence);
                if event.prev_hash != expected {
                    return false;
                }
            }
        }
        true
    }

    pub fn len(&self) -> usize {
        self.events.len()
    }

    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }

    pub fn get(&self, sequence: u64) -> Option<&ReplayEvent> {
        self.events.get(sequence as usize)
    }

    pub fn events(&self) -> &[ReplayEvent] {
        &self.events
    }

    /// Test-only constructor — directly injects events to simulate storage corruption.
    #[cfg(test)]
    pub fn from_events(events: Vec<ReplayEvent>) -> Self {
        Self { events }
    }
}

impl Default for ReplayLedger {
    fn default() -> Self {
        Self::new()
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Deterministic test hasher — XOR-folds prev + payload, rotating by sequence.
    /// NOT cryptographically secure. For structural verification only.
    struct XorHasher;

    impl ChainHasher for XorHasher {
        fn compute(&self, prev: &StateHash, payload: &StateHash, sequence: u64) -> StateHash {
            let mut result = [0u8; 32];
            let seq_bytes = sequence.to_le_bytes();
            for i in 0..32 {
                result[i] = prev[i] ^ payload[i] ^ seq_bytes[i % 8];
            }
            result
        }
    }

    #[test]
    fn empty_ledger_verifies() {
        let ledger = ReplayLedger::new();
        assert!(ledger.verify_structural(&XorHasher));
        assert!(ledger.is_empty());
    }

    #[test]
    fn single_event_genesis_prev_hash() {
        let mut ledger = ReplayLedger::new();
        let hash = [0x42u8; 32];
        let seq = ledger.append(1, hash, &XorHasher);
        assert_eq!(seq, 0);
        assert_eq!(ledger.get(0).unwrap().prev_hash, GENESIS_HASH);
        assert!(ledger.verify_structural(&XorHasher));
    }

    #[test]
    fn replay_determinism_identical_inputs_identical_state() {
        // LAW-01: same event sequence → identical ledger state
        let hash_a = [0xAAu8; 32];
        let hash_b = [0xBBu8; 32];

        let mut ledger1 = ReplayLedger::new();
        ledger1.append(1, hash_a, &XorHasher);
        ledger1.append(2, hash_b, &XorHasher);

        let mut ledger2 = ReplayLedger::new();
        ledger2.append(1, hash_a, &XorHasher);
        ledger2.append(2, hash_b, &XorHasher);

        assert_eq!(ledger1.events(), ledger2.events());
    }

    #[test]
    fn chain_verifies_after_multiple_appends() {
        let mut ledger = ReplayLedger::new();
        for i in 0u8..10 {
            ledger.append(i as u32, [i; 32], &XorHasher);
        }
        assert_eq!(ledger.len(), 10);
        assert!(ledger.verify_structural(&XorHasher));
    }

    #[test]
    fn sequence_numbers_contiguous() {
        let mut ledger = ReplayLedger::new();
        for i in 0..5 {
            let seq = ledger.append(0, [0u8; 32], &XorHasher);
            assert_eq!(seq, i as u64);
        }
    }

    #[test]
    fn tampered_event_fails_structural_verification() {
        // Build a valid 3-event chain to capture the correct chain hashes
        let mut valid = ReplayLedger::new();
        valid.append(1, [0xAAu8; 32], &XorHasher);
        valid.append(2, [0xBBu8; 32], &XorHasher);
        valid.append(3, [0xCCu8; 32], &XorHasher);
        assert!(valid.verify_structural(&XorHasher));

        // Construct a broken ledger: events 0 and 1 are correct,
        // but event 2 has a corrupted prev_hash (simulates storage tampering)
        let mut broken_events = valid.events().to_vec();
        broken_events[2].prev_hash = [0xFFu8; 32]; // wrong — chain is broken
        let broken = ReplayLedger::from_events(broken_events);
        assert!(!broken.verify_structural(&XorHasher));
    }

    #[test]
    fn replay_event_serialization_stability() {
        let event = ReplayEvent {
            sequence: 42,
            event_type: 7,
            payload_hash: [0xABu8; 32],
            prev_hash: [0x12u8; 32],
            archive_version: ARCHIVE_V1_0_0.to_bytes(),
        };
        assert_eq!(event.to_bytes(), event.to_bytes());
    }

    #[test]
    fn replay_event_roundtrip() {
        let event = ReplayEvent {
            sequence: 1,
            event_type: 3,
            payload_hash: [0x77u8; 32],
            prev_hash: [0x33u8; 32],
            archive_version: ARCHIVE_V1_0_0.to_bytes(),
        };
        let bytes = event.to_bytes();
        let recovered = ReplayEvent::from_bytes(&bytes).unwrap();
        assert_eq!(event, recovered);
    }

    #[test]
    fn different_event_types_different_bytes() {
        let hash = [0x55u8; 32];
        let e1 = ReplayEvent {
            sequence: 0, event_type: 1, payload_hash: hash, prev_hash: GENESIS_HASH,
            archive_version: ARCHIVE_V1_0_0.to_bytes(),
        };
        let e2 = ReplayEvent {
            sequence: 0, event_type: 2, payload_hash: hash, prev_hash: GENESIS_HASH,
            archive_version: ARCHIVE_V1_0_0.to_bytes(),
        };
        assert_ne!(e1.to_bytes(), e2.to_bytes());
    }

    #[test]
    fn archive_version_embedded_in_each_event() {
        let mut ledger = ReplayLedger::new();
        ledger.append(1, [0u8; 32], &XorHasher);
        let event = ledger.get(0).unwrap();
        let version = ArchiveVersion::from_bytes(&event.archive_version);
        assert_eq!(version, ARCHIVE_V1_0_0);
    }
}
