//! Gate 318 — Gossip Message Sequence Tracker: per-peer monotone sequence enforcement (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks the expected next sequence number per peer. Each incoming message carries
//! a (peer_id, sequence_number) pair. The tracker classifies it as:
//!   InOrder    — sequence == expected (advances expected by 1)
//!   Gap        — sequence > expected (gap detected; expected advances to seq+1)
//!   Duplicate  — sequence < expected (already seen or out-of-order)
//!   Reset      — sequence == 0 and expected > 0 (peer restarted)
//!
//! A Reset is accepted: expected is reset to 1 (next message after the reset).
//! All observations are hash-chained per peer for audit.
//!
//! Constants:
//!   MAX_TRACKED_PEERS: usize = 512
//!
//! SequenceEvent: InOrder | Gap | Duplicate | Reset
//!
//! SequenceRecord:
//!   peer_id, sequence, expected_before, event
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ seq_be8 ‖ expected_be8 ‖ event_byte)
//!   prev_hash
//!
//! SequenceLog: hash-chained SequenceRecords (per-peer).
//!   push(), in_order_count(), gap_count(), duplicate_count(), verify_chain().
//!
//! MessageSequenceTracker:
//!   observe(peer_id, sequence) → Result<SequenceEvent, SeqError>
//!     Err(TooManyPeers) if peer is new and at capacity.
//!   gap_count_total() → u64
//!   duplicate_count_total() → u64
//!   reset_count_total() → u64
//!   expected_sequence(peer_id) → Option<u64>
//!   get_log(peer_id) → Option<&SequenceLog>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MAX_TRACKED_PEERS: usize = 512;

// ─── Sequence event ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SequenceEvent {
    InOrder   = 0,
    Gap       = 1,
    Duplicate = 2,
    Reset     = 3,
}

impl SequenceEvent {
    pub fn event_byte(self) -> u8 { self as u8 }
}

// ─── Sequence record ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SequenceRecord {
    pub peer_id:         u32,
    pub sequence:        u64,
    pub expected_before: u64,
    pub event:           SequenceEvent,
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

pub const SEQ_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_seq_hash(
    peer_id:         u32,
    sequence:        u64,
    expected_before: u64,
    event:           SequenceEvent,
    prev:            &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(sequence.to_be_bytes());
    h.update(expected_before.to_be_bytes());
    h.update([event.event_byte()]);
    h.finalize().into()
}

pub fn build_sequence_record(
    peer_id:         u32,
    sequence:        u64,
    expected_before: u64,
    event:           SequenceEvent,
    prev_hash:       &[u8; 32],
) -> SequenceRecord {
    let record_hash = compute_seq_hash(peer_id, sequence, expected_before, event, prev_hash);
    SequenceRecord { peer_id, sequence, expected_before, event, record_hash, prev_hash: *prev_hash }
}

// ─── Sequence log (per-peer) ──────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SequenceLog {
    records: Vec<SequenceRecord>,
}

impl SequenceLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[SequenceRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(SEQ_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        peer_id:         u32,
        sequence:        u64,
        expected_before: u64,
        event:           SequenceEvent,
    ) -> &SequenceRecord {
        let prev = self.last_hash();
        let r = build_sequence_record(peer_id, sequence, expected_before, event, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn in_order_count(&self) -> usize {
        self.records.iter().filter(|r| r.event == SequenceEvent::InOrder).count()
    }

    pub fn gap_count(&self) -> usize {
        self.records.iter().filter(|r| r.event == SequenceEvent::Gap).count()
    }

    pub fn duplicate_count(&self) -> usize {
        self.records.iter().filter(|r| r.event == SequenceEvent::Duplicate).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SEQ_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_seq_hash(r.peer_id, r.sequence, r.expected_before, r.event, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for SequenceLog {
    fn default() -> Self { Self::new() }
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug, PartialEq, Eq)]
pub enum SeqError {
    TooManyPeers,
}

// ─── MessageSequenceTracker ───────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MessageSequenceTracker {
    // peer_id → expected_next_sequence
    peers:                  BTreeMap<u32, u64>,
    gap_count_total:        u64,
    duplicate_count_total:  u64,
    reset_count_total:      u64,
    pub logs:               BTreeMap<u32, SequenceLog>,
}

impl MessageSequenceTracker {
    pub fn new() -> Self {
        Self {
            peers: BTreeMap::new(),
            gap_count_total: 0,
            duplicate_count_total: 0,
            reset_count_total: 0,
            logs: BTreeMap::new(),
        }
    }

    /// Observe a (peer_id, sequence) message. Returns the classified event.
    pub fn observe(&mut self, peer_id: u32, sequence: u64) -> Result<SequenceEvent, SeqError> {
        let is_new = !self.peers.contains_key(&peer_id);
        if is_new && self.peers.len() >= MAX_TRACKED_PEERS {
            return Err(SeqError::TooManyPeers);
        }

        let expected = *self.peers.get(&peer_id).unwrap_or(&0);

        let event = if sequence == 0 && expected > 0 {
            // Peer reset
            SequenceEvent::Reset
        } else if sequence == expected {
            SequenceEvent::InOrder
        } else if sequence > expected {
            SequenceEvent::Gap
        } else {
            SequenceEvent::Duplicate
        };

        // Advance expected
        match event {
            SequenceEvent::InOrder  => { self.peers.insert(peer_id, sequence + 1); }
            SequenceEvent::Gap      => { self.peers.insert(peer_id, sequence + 1); self.gap_count_total += 1; }
            SequenceEvent::Duplicate => { self.duplicate_count_total += 1; }
            SequenceEvent::Reset    => { self.peers.insert(peer_id, 1); self.reset_count_total += 1; }
        }

        let log = self.logs.entry(peer_id).or_insert_with(SequenceLog::new);
        log.push(peer_id, sequence, expected, event);
        Ok(event)
    }

    pub fn expected_sequence(&self, peer_id: u32) -> Option<u64> {
        self.peers.get(&peer_id).copied()
    }

    pub fn gap_count_total(&self)       -> u64 { self.gap_count_total }
    pub fn duplicate_count_total(&self) -> u64 { self.duplicate_count_total }
    pub fn reset_count_total(&self)     -> u64 { self.reset_count_total }

    pub fn get_log(&self, peer_id: u32) -> Option<&SequenceLog> {
        self.logs.get(&peer_id)
    }
}

impl Default for MessageSequenceTracker {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── SequenceEvent ─────────────────────────────────────────────────────────

    #[test]
    fn event_bytes() {
        assert_eq!(SequenceEvent::InOrder.event_byte(),   0);
        assert_eq!(SequenceEvent::Gap.event_byte(),       1);
        assert_eq!(SequenceEvent::Duplicate.event_byte(), 2);
        assert_eq!(SequenceEvent::Reset.event_byte(),     3);
    }

    // ── build_sequence_record ─────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_sequence_record(1, 0, 0, SequenceEvent::InOrder, &SEQ_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_sequence_record(1, 5, 5, SequenceEvent::InOrder, &SEQ_GENESIS_HASH);
        let r2 = build_sequence_record(1, 5, 5, SequenceEvent::InOrder, &SEQ_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── SequenceLog ───────────────────────────────────────────────────────────

    #[test]
    fn log_counts() {
        let mut l = SequenceLog::new();
        l.push(1, 0, 0, SequenceEvent::InOrder);
        l.push(1, 2, 1, SequenceEvent::Gap);
        l.push(1, 1, 3, SequenceEvent::Duplicate);
        assert_eq!(l.in_order_count(),   1);
        assert_eq!(l.gap_count(),        1);
        assert_eq!(l.duplicate_count(),  1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = SequenceLog::new();
        l.push(1, 0, 0, SequenceEvent::InOrder);
        l.push(1, 1, 1, SequenceEvent::InOrder);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = SequenceLog::new();
        for i in 0..5u64 {
            l.push(1, i, i, SequenceEvent::InOrder);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── MessageSequenceTracker ────────────────────────────────────────────────

    #[test]
    fn first_message_is_in_order() {
        let mut t = MessageSequenceTracker::new();
        // First message from new peer starts at 0
        assert_eq!(t.observe(1, 0).unwrap(), SequenceEvent::InOrder);
        assert_eq!(t.expected_sequence(1), Some(1));
    }

    #[test]
    fn sequential_messages_in_order() {
        let mut t = MessageSequenceTracker::new();
        t.observe(1, 0).unwrap();
        assert_eq!(t.observe(1, 1).unwrap(), SequenceEvent::InOrder);
        assert_eq!(t.observe(1, 2).unwrap(), SequenceEvent::InOrder);
        assert_eq!(t.expected_sequence(1), Some(3));
    }

    #[test]
    fn gap_detected() {
        let mut t = MessageSequenceTracker::new();
        t.observe(1, 0).unwrap();
        // Skip 1, send 5
        assert_eq!(t.observe(1, 5).unwrap(), SequenceEvent::Gap);
        assert_eq!(t.gap_count_total(), 1);
        assert_eq!(t.expected_sequence(1), Some(6));
    }

    #[test]
    fn duplicate_detected() {
        let mut t = MessageSequenceTracker::new();
        t.observe(1, 0).unwrap();
        t.observe(1, 1).unwrap(); // expected = 2
        // Replay of seq=1 (< expected=2, not zero → Duplicate)
        assert_eq!(t.observe(1, 1).unwrap(), SequenceEvent::Duplicate);
        assert_eq!(t.duplicate_count_total(), 1);
        assert_eq!(t.expected_sequence(1), Some(2)); // unchanged
    }

    #[test]
    fn reset_detected() {
        let mut t = MessageSequenceTracker::new();
        t.observe(1, 0).unwrap();
        t.observe(1, 1).unwrap(); // expected = 2
        assert_eq!(t.observe(1, 0).unwrap(), SequenceEvent::Reset);
        assert_eq!(t.reset_count_total(), 1);
        assert_eq!(t.expected_sequence(1), Some(1)); // reset to 1
    }

    #[test]
    fn log_records_all_events() {
        let mut t = MessageSequenceTracker::new();
        t.observe(1, 0).unwrap();  // InOrder, expected→1
        t.observe(1, 5).unwrap();  // Gap (5 > 1), expected→6
        t.observe(1, 3).unwrap();  // Duplicate (3 < 6, not zero)
        let log = t.get_log(1).unwrap();
        assert_eq!(log.in_order_count(),  1);
        assert_eq!(log.gap_count(),       1);
        assert_eq!(log.duplicate_count(), 1);
        let (valid, _) = log.verify_chain();
        assert!(valid);
    }

    #[test]
    fn unknown_peer_returns_none() {
        let t = MessageSequenceTracker::new();
        assert_eq!(t.expected_sequence(99), None);
    }
}
