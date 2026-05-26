//! Gate 274 — Gossip Backpressure Monitor: per-peer rate tracking and backpressure (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks the incoming message rate per peer over a rolling window and
//! emits backpressure decisions: Accept / Throttle / Drop.
//!
//! PeerRateRecord:
//!   peer_id       — u32
//!   epoch         — u64
//!   message_count — u32 (messages received this epoch)
//!   rate_pct      — u8  (message_count * 100 / capacity_per_epoch, capped at 100)
//!   decision      — BackpressureDecision
//!   record_hash   — SHA-256(prev ‖ peer_id_be4 ‖ epoch_be8 ‖ count_be4 ‖ decision_byte)
//!   prev_hash     — [u8; 32]
//!
//! BackpressureDecision:
//!   Accept   — rate_pct ≤ 70
//!   Throttle — 70 < rate_pct ≤ 100
//!   Drop     — rate_pct > 100 (capacity exceeded)
//!
//! PeerRateLog: per-peer hash-chained log of PeerRateRecords.
//!   throttle_count(), drop_count(), max_rate_pct(), verify_chain().
//!
//! BackpressureRegistry: BTreeMap<peer_id, PeerRateLog> — multi-peer tracking.
//!   record_message_batch(), peer_decision(), global_drop_count().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

// ─── Decision ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum BackpressureDecision {
    Accept   = 0,
    Throttle = 1,
    Drop     = 2,
}

/// Classify backpressure from rate_pct.
/// rate_pct is capped at u8::MAX (255) so > 100 means capacity exceeded.
pub fn classify_decision(rate_pct: u8) -> BackpressureDecision {
    if rate_pct <= 70 {
        BackpressureDecision::Accept
    } else if rate_pct <= 100 {
        BackpressureDecision::Throttle
    } else {
        BackpressureDecision::Drop
    }
}

/// Compute rate_pct = message_count * 100 / capacity, capped at 255 (saturating).
pub fn compute_rate_pct(message_count: u32, capacity_per_epoch: u32) -> u8 {
    if capacity_per_epoch == 0 { return u8::MAX; }
    let pct = (message_count as u64 * 100) / capacity_per_epoch as u64;
    pct.min(u8::MAX as u64) as u8
}

// ─── Peer rate record ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PeerRateRecord {
    pub peer_id:       u32,
    pub epoch:         u64,
    pub message_count: u32,
    pub rate_pct:      u8,
    pub decision:      BackpressureDecision,
    pub record_hash:   [u8; 32],
    pub prev_hash:     [u8; 32],
}

pub const BACKPRESSURE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_record_hash(
    peer_id:       u32,
    epoch:         u64,
    message_count: u32,
    decision:      BackpressureDecision,
    prev:          &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(message_count.to_be_bytes());
    h.update([decision as u8]);
    h.finalize().into()
}

pub fn build_record(
    peer_id:             u32,
    epoch:               u64,
    message_count:       u32,
    capacity_per_epoch:  u32,
    prev_hash:           &[u8; 32],
) -> PeerRateRecord {
    let rate_pct = compute_rate_pct(message_count, capacity_per_epoch);
    let decision = classify_decision(rate_pct);
    let record_hash = compute_record_hash(peer_id, epoch, message_count, decision, prev_hash);
    PeerRateRecord {
        peer_id, epoch, message_count, rate_pct, decision, record_hash, prev_hash: *prev_hash,
    }
}

// ─── Per-peer rate log ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerRateLog {
    peer_id: u32,
    records: Vec<PeerRateRecord>,
}

#[derive(Debug)]
pub enum RateLogError {
    StaleEpoch,
    PeerMismatch,
}

impl PeerRateLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn peer_id(&self)  -> u32  { self.peer_id }
    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[PeerRateRecord] { &self.records }
    pub fn latest(&self)   -> Option<&PeerRateRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(BACKPRESSURE_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:              u64,
        message_count:      u32,
        capacity_per_epoch: u32,
    ) -> Result<&PeerRateRecord, RateLogError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(RateLogError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let r = build_record(self.peer_id, epoch, message_count, capacity_per_epoch, &prev_hash);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn throttle_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == BackpressureDecision::Throttle).count()
    }

    pub fn drop_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == BackpressureDecision::Drop).count()
    }

    pub fn max_rate_pct(&self) -> u8 {
        self.records.iter().map(|r| r.rate_pct).max().unwrap_or(0)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = BACKPRESSURE_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_record_hash(
                r.peer_id, r.epoch, r.message_count, r.decision, &r.prev_hash);
            if recomputed != r.record_hash {
                return (false, Some(i));
            }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Backpressure registry ────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BackpressureRegistry {
    capacity_per_epoch: u32,
    peers: BTreeMap<u32, PeerRateLog>,
}

impl BackpressureRegistry {
    pub fn new(capacity_per_epoch: u32) -> Self {
        Self { capacity_per_epoch, peers: BTreeMap::new() }
    }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    pub fn record_message_batch(
        &mut self,
        peer_id:       u32,
        epoch:         u64,
        message_count: u32,
    ) -> Result<BackpressureDecision, RateLogError> {
        let log = self.peers.entry(peer_id).or_insert_with(|| PeerRateLog::new(peer_id));
        let cap = self.capacity_per_epoch;
        let record = log.record(epoch, message_count, cap)?;
        Ok(record.decision)
    }

    /// Current decision for a peer (None if peer unseen).
    pub fn peer_decision(&self, peer_id: u32) -> Option<BackpressureDecision> {
        self.peers.get(&peer_id).and_then(|l| l.latest()).map(|r| r.decision)
    }

    /// Total Drop decisions across all peers.
    pub fn global_drop_count(&self) -> usize {
        self.peers.values().map(|l| l.drop_count()).sum()
    }

    /// Total Throttle decisions across all peers.
    pub fn global_throttle_count(&self) -> usize {
        self.peers.values().map(|l| l.throttle_count()).sum()
    }
}

impl Default for BackpressureRegistry {
    fn default() -> Self { Self::new(100) }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── helpers ───────────────────────────────────────────────────────────────

    // ── classify_decision ─────────────────────────────────────────────────────

    #[test]
    fn accept_at_or_below_70() {
        assert_eq!(classify_decision(0),  BackpressureDecision::Accept);
        assert_eq!(classify_decision(70), BackpressureDecision::Accept);
    }

    #[test]
    fn throttle_between_71_and_100() {
        assert_eq!(classify_decision(71),  BackpressureDecision::Throttle);
        assert_eq!(classify_decision(100), BackpressureDecision::Throttle);
    }

    #[test]
    fn drop_above_100() {
        assert_eq!(classify_decision(101), BackpressureDecision::Drop);
        assert_eq!(classify_decision(255), BackpressureDecision::Drop);
    }

    // ── compute_rate_pct ──────────────────────────────────────────────────────

    #[test]
    fn rate_pct_zero_capacity_is_max() {
        assert_eq!(compute_rate_pct(100, 0), u8::MAX);
    }

    #[test]
    fn rate_pct_exact_capacity() {
        assert_eq!(compute_rate_pct(100, 100), 100);
    }

    #[test]
    fn rate_pct_below_capacity() {
        assert_eq!(compute_rate_pct(50, 100), 50);
    }

    #[test]
    fn rate_pct_over_capacity_capped_at_255() {
        assert_eq!(compute_rate_pct(500, 100), 255);
    }

    // ── build_record ──────────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_record(1, 1, 50, 100, &BACKPRESSURE_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_record(1, 1, 50, 100, &BACKPRESSURE_GENESIS_HASH);
        let r2 = build_record(1, 1, 50, 100, &BACKPRESSURE_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn accept_record_has_correct_decision() {
        let r = build_record(1, 1, 50, 100, &BACKPRESSURE_GENESIS_HASH);
        assert_eq!(r.decision, BackpressureDecision::Accept);
        assert_eq!(r.rate_pct, 50);
    }

    #[test]
    fn drop_record_when_over_capacity() {
        let r = build_record(1, 1, 200, 100, &BACKPRESSURE_GENESIS_HASH);
        assert_eq!(r.decision, BackpressureDecision::Drop);
    }

    // ── PeerRateLog ───────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = PeerRateLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.throttle_count(), 0);
        assert_eq!(l.drop_count(), 0);
        assert_eq!(l.max_rate_pct(), 0);
    }

    #[test]
    fn record_appends_and_chains() {
        let mut l = PeerRateLog::new(1);
        l.record(1, 50, 100).unwrap();
        l.record(2, 80, 100).unwrap();
        assert_eq!(l.len(), 2);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = PeerRateLog::new(1);
        l.record(5, 50, 100).unwrap();
        assert!(matches!(l.record(5, 50, 100), Err(RateLogError::StaleEpoch)));
    }

    #[test]
    fn throttle_and_drop_counts() {
        let mut l = PeerRateLog::new(1);
        l.record(1, 50,  100).unwrap(); // Accept
        l.record(2, 80,  100).unwrap(); // Throttle
        l.record(3, 150, 100).unwrap(); // Drop
        assert_eq!(l.throttle_count(), 1);
        assert_eq!(l.drop_count(),     1);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = PeerRateLog::new(1);
        for i in 1..=5u64 {
            l.record(i, 40 + i as u32 * 10, 100).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── BackpressureRegistry ──────────────────────────────────────────────────

    #[test]
    fn new_registry_empty() {
        let r = BackpressureRegistry::new(100);
        assert_eq!(r.peer_count(), 0);
        assert_eq!(r.global_drop_count(), 0);
    }

    #[test]
    fn record_batch_creates_peer() {
        let mut r = BackpressureRegistry::new(100);
        let d = r.record_message_batch(1, 1, 50).unwrap();
        assert_eq!(d, BackpressureDecision::Accept);
        assert_eq!(r.peer_count(), 1);
    }

    #[test]
    fn global_drop_count_aggregates() {
        let mut r = BackpressureRegistry::new(100);
        r.record_message_batch(1, 1, 200).unwrap(); // Drop
        r.record_message_batch(2, 1, 50).unwrap();  // Accept
        r.record_message_batch(3, 1, 150).unwrap(); // Drop
        assert_eq!(r.global_drop_count(), 2);
    }

    #[test]
    fn peer_decision_reflects_latest() {
        let mut r = BackpressureRegistry::new(100);
        r.record_message_batch(1, 1, 80).unwrap();  // Throttle
        r.record_message_batch(1, 2, 40).unwrap();  // Accept
        assert_eq!(r.peer_decision(1), Some(BackpressureDecision::Accept));
    }

    #[test]
    fn unknown_peer_decision_is_none() {
        let r = BackpressureRegistry::new(100);
        assert_eq!(r.peer_decision(99), None);
    }
}
