//! Gate 393 — Gossip Peer Churn Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks peer join/leave events per epoch to detect network instability.
//! churn_count = joins + leaves per epoch. High churn indicates unstable mesh.
//!
//! GossipPeerChurnEntry (hash-chained):
//!   epoch_end:   u64
//!   joins:       u32  — peers that joined this epoch
//!   leaves:      u32  — peers that left this epoch
//!   churn_count: u32  — joins + leaves (saturating_add)
//!   entry_hash:  [u8;32]
//!   prev_hash:   [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ joins_be4
//!                       ‖ leaves_be4 ‖ churn_count_be4)
//!
//! GossipPeerChurnLog: record(epoch_end, joins, leaves),
//!   total_joins(), total_leaves(), max_churn(), average_churn(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_PEER_CHURN_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipPeerChurnEntry ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerChurnEntry {
    pub epoch_end:   u64,
    pub joins:       u32,
    pub leaves:      u32,
    pub churn_count: u32,
    pub entry_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

fn compute_peer_churn_hash(
    prev:        &[u8; 32],
    epoch_end:   u64,
    joins:       u32,
    leaves:      u32,
    churn_count: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(joins.to_be_bytes());
    h.update(leaves.to_be_bytes());
    h.update(churn_count.to_be_bytes());
    h.finalize().into()
}

// ─── GossipPeerChurnLog ───────────────────────────────────────────────────────

pub struct GossipPeerChurnLog {
    entries: Vec<GossipPeerChurnEntry>,
}

impl GossipPeerChurnLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipPeerChurnEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipPeerChurnEntry> { self.entries.last() }

    /// Total joins across all epochs.
    pub fn total_joins(&self) -> u64 {
        self.entries.iter().map(|e| e.joins as u64).sum()
    }

    /// Total leaves across all epochs.
    pub fn total_leaves(&self) -> u64 {
        self.entries.iter().map(|e| e.leaves as u64).sum()
    }

    /// Maximum churn_count in a single epoch. Returns 0 if empty.
    pub fn max_churn(&self) -> u32 {
        self.entries.iter().map(|e| e.churn_count).max().unwrap_or(0)
    }

    /// Average churn_count across all epochs (floor division). Returns 0 if empty.
    pub fn average_churn(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u32 = self.entries.iter().map(|e| e.churn_count).sum();
        sum / self.entries.len() as u32
    }

    /// Record peer churn for one epoch.
    /// churn_count = joins.saturating_add(leaves).
    pub fn record(
        &mut self,
        epoch_end: u64,
        joins:     u32,
        leaves:    u32,
    ) -> &GossipPeerChurnEntry {
        let churn_count = joins.saturating_add(leaves);

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PEER_CHURN_GENESIS_HASH);

        let entry_hash = compute_peer_churn_hash(&prev, epoch_end, joins, leaves, churn_count);

        self.entries.push(GossipPeerChurnEntry {
            epoch_end,
            joins,
            leaves,
            churn_count,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PEER_CHURN_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_peer_churn_hash(
                &prev, e.epoch_end, e.joins, e.leaves, e.churn_count,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerChurnLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipPeerChurnLog::new();
        let e = log.record(5, 3, 2);
        assert_eq!(e.epoch_end, 5);
        assert_eq!(e.joins, 3);
        assert_eq!(e.leaves, 2);
        assert_eq!(e.churn_count, 5);
    }

    #[test]
    fn zero_churn_recorded() {
        let mut log = GossipPeerChurnLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.churn_count, 0);
    }

    #[test]
    fn churn_count_saturates() {
        let mut log = GossipPeerChurnLog::new();
        let e = log.record(1, u32::MAX, 1);
        assert_eq!(e.churn_count, u32::MAX);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn total_joins_correct() {
        let mut log = GossipPeerChurnLog::new();
        log.record(1, 3, 1);
        log.record(2, 5, 2);
        log.record(3, 2, 0);
        assert_eq!(log.total_joins(), 10);
    }

    #[test]
    fn total_leaves_correct() {
        let mut log = GossipPeerChurnLog::new();
        log.record(1, 3, 1);
        log.record(2, 5, 4);
        assert_eq!(log.total_leaves(), 5);
    }

    #[test]
    fn max_churn_correct() {
        let mut log = GossipPeerChurnLog::new();
        log.record(1, 2, 1); // churn=3
        log.record(2, 8, 7); // churn=15
        log.record(3, 1, 2); // churn=3
        assert_eq!(log.max_churn(), 15);
    }

    #[test]
    fn max_churn_empty_zero() {
        let log = GossipPeerChurnLog::new();
        assert_eq!(log.max_churn(), 0);
    }

    #[test]
    fn average_churn_correct() {
        let mut log = GossipPeerChurnLog::new();
        log.record(1, 3, 3); // churn=6
        log.record(2, 2, 2); // churn=4
        log.record(3, 5, 5); // churn=10
        // avg = (6+4+10)/3 = 6
        assert_eq!(log.average_churn(), 6);
    }

    #[test]
    fn average_churn_empty_zero() {
        let log = GossipPeerChurnLog::new();
        assert_eq!(log.average_churn(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPeerChurnLog::new();
        let e = log.record(1, 2, 1);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipPeerChurnLog::new();
        let e = log.record(1, 2, 1);
        assert_eq!(e.prev_hash, GOSSIP_PEER_CHURN_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPeerChurnLog::new();
        log.record(1, 2, 1);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 3, 2);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPeerChurnLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPeerChurnLog::new();
        for i in 1u64..=5 { log.record(i, i as u32, i as u32); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPeerChurnLog::new();
        log.record(1, 2, 1);
        log.record(2, 3, 2);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipPeerChurnLog::new();
        let mut l2 = GossipPeerChurnLog::new();
        let h1 = l1.record(5, 3, 2).entry_hash;
        let h2 = l2.record(5, 3, 2).entry_hash;
        assert_eq!(h1, h2);
    }
}
