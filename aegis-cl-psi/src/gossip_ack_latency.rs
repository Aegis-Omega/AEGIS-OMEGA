//! Gate 391 — Gossip Acknowledgment Latency Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks per-peer acknowledgment latency in epochs (ack_epoch - dispatch_epoch).
//! Maintains rolling window (size 4) for per-peer average latency.
//! High ack latency indicates slow or unreliable peers.
//!
//! GossipAckLatencyEntry (hash-chained):
//!   peer_id:        u64
//!   epoch:          u64   — epoch of acknowledgment
//!   latency_epochs: u64   — ack_epoch - dispatch_epoch (saturating_sub)
//!   rolling_avg:    u64   — integer avg over window (floor division)
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ peer_id_be8 ‖ epoch_be8
//!                       ‖ latency_epochs_be8 ‖ rolling_avg_be8)
//!
//! GossipAckLatencyLog: record(peer_id, dispatch_epoch, ack_epoch),
//!   avg_latency_for(peer_id), max_latency(), overall_avg(), verify_chain().

use std::collections::BTreeMap;
use sha2::{Sha256, Digest};

pub const GOSSIP_ACK_LATENCY_GENESIS_HASH: [u8; 32] = [0u8; 32];
const WINDOW_SIZE: usize = 4;

// ─── GossipAckLatencyEntry ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipAckLatencyEntry {
    pub peer_id:        u64,
    pub epoch:          u64,
    pub latency_epochs: u64,
    pub rolling_avg:    u64,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_ack_latency_hash(
    prev:           &[u8; 32],
    peer_id:        u64,
    epoch:          u64,
    latency_epochs: u64,
    rolling_avg:    u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(latency_epochs.to_be_bytes());
    h.update(rolling_avg.to_be_bytes());
    h.finalize().into()
}

// ─── GossipAckLatencyLog ──────────────────────────────────────────────────────

pub struct GossipAckLatencyLog {
    entries: Vec<GossipAckLatencyEntry>,
    // BTreeMap: peer_id → rolling window of recent latency values
    peer_windows: BTreeMap<u64, Vec<u64>>,
}

impl GossipAckLatencyLog {
    pub fn new() -> Self {
        Self {
            entries:      Vec::new(),
            peer_windows: BTreeMap::new(),
        }
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipAckLatencyEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipAckLatencyEntry> { self.entries.last() }

    /// Average latency for a specific peer across all recorded entries. Returns 0 if unknown.
    pub fn avg_latency_for(&self, peer_id: u64) -> u64 {
        let peer_entries: Vec<u64> = self.entries.iter()
            .filter(|e| e.peer_id == peer_id)
            .map(|e| e.latency_epochs)
            .collect();
        if peer_entries.is_empty() {
            return 0;
        }
        let sum: u64 = peer_entries.iter().sum();
        sum / peer_entries.len() as u64
    }

    /// Maximum latency_epochs seen across all entries. Returns 0 if empty.
    pub fn max_latency(&self) -> u64 {
        self.entries.iter().map(|e| e.latency_epochs).max().unwrap_or(0)
    }

    /// Overall average latency across all entries and peers. Returns 0 if empty.
    pub fn overall_avg(&self) -> u64 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.latency_epochs).sum();
        sum / self.entries.len() as u64
    }

    /// Record an ack latency event for a peer.
    /// latency_epochs = ack_epoch.saturating_sub(dispatch_epoch).
    pub fn record(
        &mut self,
        peer_id:        u64,
        dispatch_epoch: u64,
        ack_epoch:      u64,
    ) -> &GossipAckLatencyEntry {
        let latency_epochs = ack_epoch.saturating_sub(dispatch_epoch);

        // Update rolling window for this peer
        let window = self.peer_windows.entry(peer_id).or_insert_with(Vec::new);
        window.push(latency_epochs);
        if window.len() > WINDOW_SIZE {
            window.remove(0);
        }
        let rolling_avg = {
            let s: u64 = window.iter().sum();
            s / window.len() as u64
        };

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_ACK_LATENCY_GENESIS_HASH);

        let entry_hash = compute_ack_latency_hash(
            &prev, peer_id, ack_epoch, latency_epochs, rolling_avg,
        );

        self.entries.push(GossipAckLatencyEntry {
            peer_id,
            epoch: ack_epoch,
            latency_epochs,
            rolling_avg,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_ACK_LATENCY_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_ack_latency_hash(
                &prev, e.peer_id, e.epoch, e.latency_epochs, e.rolling_avg,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipAckLatencyLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipAckLatencyLog::new();
        let e = log.record(1, 5, 8);
        assert_eq!(e.peer_id, 1);
        assert_eq!(e.epoch, 8);
        assert_eq!(e.latency_epochs, 3);
    }

    #[test]
    fn zero_latency_when_same_epoch() {
        let mut log = GossipAckLatencyLog::new();
        let e = log.record(1, 5, 5);
        assert_eq!(e.latency_epochs, 0);
    }

    #[test]
    fn saturating_sub_when_ack_before_dispatch() {
        let mut log = GossipAckLatencyLog::new();
        // ack_epoch < dispatch_epoch → saturating_sub → 0
        let e = log.record(1, 10, 5);
        assert_eq!(e.latency_epochs, 0);
    }

    // ── rolling average ───────────────────────────────────────────────────────

    #[test]
    fn rolling_avg_single_entry() {
        let mut log = GossipAckLatencyLog::new();
        let e = log.record(1, 0, 4); // latency=4
        assert_eq!(e.rolling_avg, 4);
    }

    #[test]
    fn rolling_avg_window_fills() {
        let mut log = GossipAckLatencyLog::new();
        log.record(1, 0, 2); // latency=2, window=[2], avg=2
        log.record(1, 0, 4); // latency=4, window=[2,4], avg=3
        log.record(1, 0, 6); // latency=6, window=[2,4,6], avg=4
        let e = log.record(1, 0, 8); // latency=8, window=[2,4,6,8], avg=5
        assert_eq!(e.rolling_avg, 5);
    }

    #[test]
    fn rolling_avg_window_evicts_oldest() {
        let mut log = GossipAckLatencyLog::new();
        log.record(1, 0, 2);  // latency=2
        log.record(1, 0, 4);  // latency=4
        log.record(1, 0, 6);  // latency=6
        log.record(1, 0, 8);  // latency=8, window=[2,4,6,8], avg=5
        let e = log.record(1, 0, 10); // latency=10, window=[4,6,8,10], avg=7
        assert_eq!(e.rolling_avg, 7);
    }

    #[test]
    fn rolling_avg_per_peer_independent() {
        let mut log = GossipAckLatencyLog::new();
        log.record(1, 0, 10); // peer 1: latency=10
        let e2 = log.record(2, 0, 2); // peer 2: latency=2
        // peer 2 should have its own window
        assert_eq!(e2.rolling_avg, 2);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn avg_latency_for_accumulates() {
        let mut log = GossipAckLatencyLog::new();
        log.record(1, 0, 2);  // latency=2
        log.record(1, 0, 4);  // latency=4
        log.record(1, 0, 6);  // latency=6
        // avg = (2+4+6)/3 = 4
        assert_eq!(log.avg_latency_for(1), 4);
    }

    #[test]
    fn avg_latency_for_unknown_peer_zero() {
        let log = GossipAckLatencyLog::new();
        assert_eq!(log.avg_latency_for(99), 0);
    }

    #[test]
    fn max_latency_correct() {
        let mut log = GossipAckLatencyLog::new();
        log.record(1, 0, 3);
        log.record(2, 0, 10);
        log.record(3, 0, 7);
        assert_eq!(log.max_latency(), 10);
    }

    #[test]
    fn max_latency_empty_zero() {
        let log = GossipAckLatencyLog::new();
        assert_eq!(log.max_latency(), 0);
    }

    #[test]
    fn overall_avg_correct() {
        let mut log = GossipAckLatencyLog::new();
        log.record(1, 0, 4);  // latency=4
        log.record(2, 0, 8);  // latency=8
        // avg = (4+8)/2 = 6
        assert_eq!(log.overall_avg(), 6);
    }

    #[test]
    fn overall_avg_empty_zero() {
        let log = GossipAckLatencyLog::new();
        assert_eq!(log.overall_avg(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipAckLatencyLog::new();
        let e = log.record(1, 0, 5);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipAckLatencyLog::new();
        let e = log.record(1, 0, 5);
        assert_eq!(e.prev_hash, GOSSIP_ACK_LATENCY_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipAckLatencyLog::new();
        log.record(1, 0, 3);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 0, 5);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipAckLatencyLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipAckLatencyLog::new();
        for i in 1u64..=5 { log.record(i, 0, i * 2); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipAckLatencyLog::new();
        log.record(1, 0, 3);
        log.record(2, 0, 5);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipAckLatencyLog::new();
        let mut l2 = GossipAckLatencyLog::new();
        let h1 = l1.record(3, 1, 7).entry_hash;
        let h2 = l2.record(3, 1, 7).entry_hash;
        assert_eq!(h1, h2);
    }
}
