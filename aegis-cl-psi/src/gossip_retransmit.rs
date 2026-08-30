//! Gate 390 — Gossip Retransmit Counter (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks per-epoch gossip retransmit attempts — frames re-sent after an
//! initial delivery failure. High retransmit counts indicate persistent
//! delivery problems for specific peers.
//!
//! GossipRetransmitEntry (hash-chained):
//!   epoch_end:       u64
//!   peer_id:         u64   — peer that required retransmission
//!   retransmit_count: u32  — number of retransmit attempts for this peer this epoch
//!   entry_hash:      [u8;32]
//!   prev_hash:       [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ peer_id_be8
//!                        ‖ retransmit_count_be4)
//!
//! GossipRetransmitLog: record(epoch_end, peer_id, retransmit_count),
//!   latest(), entry_count(), total_retransmits(), max_retransmits(),
//!   peer_total(peer_id), verify_chain().

use std::collections::BTreeMap;
use sha2::{Sha256, Digest};

pub const GOSSIP_RETRANSMIT_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipRetransmitEntry ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipRetransmitEntry {
    pub epoch_end:        u64,
    pub peer_id:          u64,
    pub retransmit_count: u32,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_retransmit_hash(
    prev:             &[u8; 32],
    epoch_end:        u64,
    peer_id:          u64,
    retransmit_count: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(peer_id.to_be_bytes());
    h.update(retransmit_count.to_be_bytes());
    h.finalize().into()
}

// ─── GossipRetransmitLog ──────────────────────────────────────────────────────

pub struct GossipRetransmitLog {
    entries:     Vec<GossipRetransmitEntry>,
    // BTreeMap: peer_id → cumulative retransmit_count
    peer_totals: BTreeMap<u64, u64>,
}

impl GossipRetransmitLog {
    pub fn new() -> Self {
        Self {
            entries:     Vec::new(),
            peer_totals: BTreeMap::new(),
        }
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipRetransmitEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipRetransmitEntry> { self.entries.last() }

    /// Total retransmit_count across all entries (all peers, all epochs).
    pub fn total_retransmits(&self) -> u64 {
        self.entries.iter().map(|e| e.retransmit_count as u64).sum()
    }

    /// Maximum retransmit_count in a single entry. Returns 0 if empty.
    pub fn max_retransmits(&self) -> u32 {
        self.entries.iter().map(|e| e.retransmit_count).max().unwrap_or(0)
    }

    /// Cumulative retransmit count for a specific peer. Returns 0 if unknown.
    pub fn peer_total(&self, peer_id: u64) -> u64 {
        self.peer_totals.get(&peer_id).copied().unwrap_or(0)
    }

    /// Record retransmit count for a peer during one epoch.
    pub fn record(
        &mut self,
        epoch_end:        u64,
        peer_id:          u64,
        retransmit_count: u32,
    ) -> &GossipRetransmitEntry {
        *self.peer_totals.entry(peer_id).or_insert(0) += retransmit_count as u64;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_RETRANSMIT_GENESIS_HASH);

        let entry_hash = compute_retransmit_hash(&prev, epoch_end, peer_id, retransmit_count);

        self.entries.push(GossipRetransmitEntry {
            epoch_end,
            peer_id,
            retransmit_count,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_RETRANSMIT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_retransmit_hash(
                &prev, e.epoch_end, e.peer_id, e.retransmit_count,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipRetransmitLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record ────────────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipRetransmitLog::new();
        let e = log.record(5, 3, 7);
        assert_eq!(e.epoch_end, 5);
        assert_eq!(e.peer_id, 3);
        assert_eq!(e.retransmit_count, 7);
    }

    #[test]
    fn zero_retransmits_recorded() {
        let mut log = GossipRetransmitLog::new();
        let e = log.record(1, 1, 0);
        assert_eq!(e.retransmit_count, 0);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn total_retransmits_sums_all() {
        let mut log = GossipRetransmitLog::new();
        log.record(1, 1, 3);
        log.record(2, 2, 5);
        log.record(3, 1, 2);
        assert_eq!(log.total_retransmits(), 10);
    }

    #[test]
    fn total_retransmits_empty_zero() {
        let log = GossipRetransmitLog::new();
        assert_eq!(log.total_retransmits(), 0);
    }

    #[test]
    fn max_retransmits_correct() {
        let mut log = GossipRetransmitLog::new();
        log.record(1, 1, 3);
        log.record(2, 2, 10);
        log.record(3, 3, 5);
        assert_eq!(log.max_retransmits(), 10);
    }

    #[test]
    fn max_retransmits_empty_zero() {
        let log = GossipRetransmitLog::new();
        assert_eq!(log.max_retransmits(), 0);
    }

    #[test]
    fn peer_total_accumulates() {
        let mut log = GossipRetransmitLog::new();
        log.record(1, 1, 3);
        log.record(2, 1, 5);
        log.record(3, 2, 4);
        assert_eq!(log.peer_total(1), 8);
        assert_eq!(log.peer_total(2), 4);
    }

    #[test]
    fn peer_total_unknown_peer_zero() {
        let log = GossipRetransmitLog::new();
        assert_eq!(log.peer_total(99), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipRetransmitLog::new();
        let e = log.record(1, 1, 3);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipRetransmitLog::new();
        let e = log.record(1, 1, 3);
        assert_eq!(e.prev_hash, GOSSIP_RETRANSMIT_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipRetransmitLog::new();
        log.record(1, 1, 3);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 2, 5);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipRetransmitLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipRetransmitLog::new();
        for i in 1u64..=5 { log.record(i, i, i as u32); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipRetransmitLog::new();
        log.record(1, 1, 3);
        log.record(2, 2, 5);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipRetransmitLog::new();
        let mut l2 = GossipRetransmitLog::new();
        let h1 = l1.record(5, 3, 7).entry_hash;
        let h2 = l2.record(5, 3, 7).entry_hash;
        assert_eq!(h1, h2);
    }
}
