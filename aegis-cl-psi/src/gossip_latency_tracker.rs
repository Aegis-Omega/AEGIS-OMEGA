//! Gate 379 — Gossip Latency Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks synthetic per-peer latency as the epoch delta between when a frame
//! was dispatched and when the peer's sync state last acknowledged it.
//! Latency is represented as an integer epoch count (no wall-clock time —
//! determinism invariant).
//!
//! GossipLatencyRecord:
//!   peer_id:          u64
//!   dispatch_epoch:   u64   — epoch at which frame was dispatched
//!   ack_epoch:        u64   — epoch at which peer acknowledged
//!   latency_epochs:   u64   — ack_epoch.saturating_sub(dispatch_epoch)
//!   record_hash:      [u8;32]
//!   prev_hash:        [u8;32]
//!
//! record_hash = SHA-256(prev[32] ‖ peer_id_be8 ‖ dispatch_epoch_be8
//!                         ‖ ack_epoch_be8 ‖ latency_epochs_be8)
//!
//! GossipLatencyLog: record(peer_id, dispatch_epoch, ack_epoch),
//!   record_count(), max_latency(), min_latency(), avg_latency(),
//!   latest(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_LATENCY_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipLatencyRecord ──────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipLatencyRecord {
    pub peer_id:        u64,
    pub dispatch_epoch: u64,
    pub ack_epoch:      u64,
    pub latency_epochs: u64,
    pub record_hash:    [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_latency_hash(
    prev:           &[u8; 32],
    peer_id:        u64,
    dispatch_epoch: u64,
    ack_epoch:      u64,
    latency_epochs: u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(dispatch_epoch.to_be_bytes());
    h.update(ack_epoch.to_be_bytes());
    h.update(latency_epochs.to_be_bytes());
    h.finalize().into()
}

// ─── GossipLatencyLog ─────────────────────────────────────────────────────────

pub struct GossipLatencyLog {
    records: Vec<GossipLatencyRecord>,
}

impl GossipLatencyLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn record_count(&self) -> usize { self.records.len() }
    pub fn is_empty(&self)     -> bool  { self.records.is_empty() }
    pub fn records(&self)      -> &[GossipLatencyRecord] { &self.records }
    pub fn latest(&self)       -> Option<&GossipLatencyRecord> { self.records.last() }

    /// Maximum latency_epochs across all records. Returns 0 if empty.
    pub fn max_latency(&self) -> u64 {
        self.records.iter().map(|r| r.latency_epochs).max().unwrap_or(0)
    }

    /// Minimum latency_epochs across all records. Returns 0 if empty.
    pub fn min_latency(&self) -> u64 {
        self.records.iter().map(|r| r.latency_epochs).min().unwrap_or(0)
    }

    /// Integer average latency (floor). Returns 0 if empty.
    pub fn avg_latency(&self) -> u64 {
        if self.records.is_empty() { return 0; }
        let sum: u64 = self.records.iter().map(|r| r.latency_epochs).sum();
        sum / self.records.len() as u64
    }

    /// Record a latency observation for one peer.
    /// latency_epochs = ack_epoch.saturating_sub(dispatch_epoch)
    pub fn record(
        &mut self,
        peer_id:        u64,
        dispatch_epoch: u64,
        ack_epoch:      u64,
    ) -> &GossipLatencyRecord {
        let latency_epochs = ack_epoch.saturating_sub(dispatch_epoch);

        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(GOSSIP_LATENCY_GENESIS_HASH);

        let record_hash = compute_latency_hash(
            &prev, peer_id, dispatch_epoch, ack_epoch, latency_epochs,
        );

        self.records.push(GossipLatencyRecord {
            peer_id,
            dispatch_epoch,
            ack_epoch,
            latency_epochs,
            record_hash,
            prev_hash: prev,
        });
        self.records.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_LATENCY_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_latency_hash(
                &prev, r.peer_id, r.dispatch_epoch, r.ack_epoch, r.latency_epochs,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for GossipLatencyLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── latency computation ───────────────────────────────────────────────────

    #[test]
    fn latency_zero_when_same_epoch() {
        let mut log = GossipLatencyLog::new();
        let r = log.record(1, 5, 5);
        assert_eq!(r.latency_epochs, 0);
    }

    #[test]
    fn latency_computed_correctly() {
        let mut log = GossipLatencyLog::new();
        let r = log.record(1, 3, 8);
        assert_eq!(r.latency_epochs, 5);
    }

    #[test]
    fn latency_saturates_on_reverse() {
        // ack before dispatch → saturating_sub returns 0
        let mut log = GossipLatencyLog::new();
        let r = log.record(1, 10, 5);
        assert_eq!(r.latency_epochs, 0);
    }

    // ── record ────────────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipLatencyLog::new();
        let r = log.record(7, 2, 9);
        assert_eq!(r.peer_id, 7);
        assert_eq!(r.dispatch_epoch, 2);
        assert_eq!(r.ack_epoch, 9);
        assert_eq!(r.latency_epochs, 7);
    }

    #[test]
    fn record_hash_nonzero() {
        let mut log = GossipLatencyLog::new();
        let r = log.record(1, 1, 3);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn first_record_prev_hash_is_genesis() {
        let mut log = GossipLatencyLog::new();
        let r = log.record(1, 1, 2);
        assert_eq!(r.prev_hash, GOSSIP_LATENCY_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipLatencyLog::new();
        log.record(1, 1, 2);
        let h0 = log.records()[0].record_hash;
        log.record(2, 2, 4);
        assert_eq!(log.records()[1].prev_hash, h0);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn max_latency_empty() {
        let log = GossipLatencyLog::new();
        assert_eq!(log.max_latency(), 0);
    }

    #[test]
    fn max_latency_correct() {
        let mut log = GossipLatencyLog::new();
        log.record(1, 0, 3);
        log.record(2, 0, 7);
        log.record(3, 0, 2);
        assert_eq!(log.max_latency(), 7);
    }

    #[test]
    fn min_latency_correct() {
        let mut log = GossipLatencyLog::new();
        log.record(1, 0, 3);
        log.record(2, 0, 7);
        log.record(3, 0, 1);
        assert_eq!(log.min_latency(), 1);
    }

    #[test]
    fn avg_latency_floor() {
        let mut log = GossipLatencyLog::new();
        log.record(1, 0, 3); // latency=3
        log.record(2, 0, 4); // latency=4
        // sum=7, count=2, avg=3 (floor of 3.5)
        assert_eq!(log.avg_latency(), 3);
    }

    #[test]
    fn avg_latency_empty() {
        let log = GossipLatencyLog::new();
        assert_eq!(log.avg_latency(), 0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipLatencyLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_records_ok() {
        let mut log = GossipLatencyLog::new();
        for i in 1u64..=4 { log.record(i, i, i + 2); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipLatencyLog::new();
        log.record(1, 1, 3);
        log.record(2, 2, 5);
        log.records[0].record_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn record_hash_deterministic() {
        let mut l1 = GossipLatencyLog::new();
        let mut l2 = GossipLatencyLog::new();
        let h1 = l1.record(5, 2, 9).record_hash;
        let h2 = l2.record(5, 2, 9).record_hash;
        assert_eq!(h1, h2);
    }
}
