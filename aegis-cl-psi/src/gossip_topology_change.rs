//! Gate 389 — Gossip Topology Change Detector (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Detects changes in the gossip peer topology between epochs. A topology
//! change is any epoch where the peer count differs from the previous epoch.
//! Tracks the delta (signed, represented as i32) and a changed flag per
//! epoch in a hash-chained log.
//!
//! GossipTopologyChangeEntry (hash-chained):
//!   epoch_end:    u64
//!   peer_count:   u32   — total known peers at end of epoch
//!   delta:        i32   — peer_count - prev_peer_count (0 for first entry)
//!   changed:      bool  — delta != 0
//!   entry_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ peer_count_be4
//!                        ‖ delta_be4 ‖ changed_byte)
//!
//! Note: delta is serialized as i32 big-endian bytes (to_be_bytes on i32).
//!
//! GossipTopologyChangeLog: record(epoch_end, peer_count),
//!   latest(), entry_count(), change_count(), max_peer_count(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_TOPOLOGY_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipTopologyChangeEntry ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipTopologyChangeEntry {
    pub epoch_end:  u64,
    pub peer_count: u32,
    pub delta:      i32,
    pub changed:    bool,
    pub entry_hash: [u8; 32],
    pub prev_hash:  [u8; 32],
}

fn compute_topology_hash(
    prev:       &[u8; 32],
    epoch_end:  u64,
    peer_count: u32,
    delta:      i32,
    changed:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(peer_count.to_be_bytes());
    h.update(delta.to_be_bytes());
    h.update([changed as u8]);
    h.finalize().into()
}

// ─── GossipTopologyChangeLog ──────────────────────────────────────────────────

pub struct GossipTopologyChangeLog {
    entries:         Vec<GossipTopologyChangeEntry>,
    last_peer_count: Option<u32>,
}

impl GossipTopologyChangeLog {
    pub fn new() -> Self {
        Self {
            entries:         Vec::new(),
            last_peer_count: None,
        }
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipTopologyChangeEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipTopologyChangeEntry> { self.entries.last() }

    /// Count of epochs where the topology changed (delta != 0).
    pub fn change_count(&self) -> usize {
        self.entries.iter().filter(|e| e.changed).count()
    }

    /// Maximum peer_count seen across all entries. Returns 0 if empty.
    pub fn max_peer_count(&self) -> u32 {
        self.entries.iter().map(|e| e.peer_count).max().unwrap_or(0)
    }

    /// Record peer count for one epoch.
    /// delta = peer_count as i32 - prev_peer_count as i32 (0 for first entry).
    pub fn record(&mut self, epoch_end: u64, peer_count: u32) -> &GossipTopologyChangeEntry {
        let delta = match self.last_peer_count {
            None    => 0i32,
            Some(p) => peer_count as i32 - p as i32,
        };
        let changed = delta != 0;
        self.last_peer_count = Some(peer_count);

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_TOPOLOGY_GENESIS_HASH);

        let entry_hash = compute_topology_hash(&prev, epoch_end, peer_count, delta, changed);

        self.entries.push(GossipTopologyChangeEntry {
            epoch_end,
            peer_count,
            delta,
            changed,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_TOPOLOGY_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_topology_hash(
                &prev, e.epoch_end, e.peer_count, e.delta, e.changed,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipTopologyChangeLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── delta and changed ─────────────────────────────────────────────────────

    #[test]
    fn first_entry_delta_zero_not_changed() {
        let mut log = GossipTopologyChangeLog::new();
        let e = log.record(1, 10);
        assert_eq!(e.delta, 0);
        assert!(!e.changed);
    }

    #[test]
    fn delta_positive_on_peer_add() {
        let mut log = GossipTopologyChangeLog::new();
        log.record(1, 10);
        let e = log.record(2, 15);
        assert_eq!(e.delta, 5);
        assert!(e.changed);
    }

    #[test]
    fn delta_negative_on_peer_remove() {
        let mut log = GossipTopologyChangeLog::new();
        log.record(1, 10);
        let e = log.record(2, 7);
        assert_eq!(e.delta, -3);
        assert!(e.changed);
    }

    #[test]
    fn no_change_when_same_count() {
        let mut log = GossipTopologyChangeLog::new();
        log.record(1, 10);
        let e = log.record(2, 10);
        assert_eq!(e.delta, 0);
        assert!(!e.changed);
    }

    // ── change_count ──────────────────────────────────────────────────────────

    #[test]
    fn change_count_correct() {
        let mut log = GossipTopologyChangeLog::new();
        log.record(1, 10);  // delta=0, no change
        log.record(2, 12);  // delta=+2, changed
        log.record(3, 12);  // delta=0, no change
        log.record(4, 11);  // delta=-1, changed
        assert_eq!(log.change_count(), 2);
    }

    #[test]
    fn change_count_empty_zero() {
        let log = GossipTopologyChangeLog::new();
        assert_eq!(log.change_count(), 0);
    }

    // ── max_peer_count ────────────────────────────────────────────────────────

    #[test]
    fn max_peer_count_empty_zero() {
        let log = GossipTopologyChangeLog::new();
        assert_eq!(log.max_peer_count(), 0);
    }

    #[test]
    fn max_peer_count_correct() {
        let mut log = GossipTopologyChangeLog::new();
        log.record(1, 5);
        log.record(2, 20);
        log.record(3, 10);
        assert_eq!(log.max_peer_count(), 20);
    }

    // ── fields ────────────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipTopologyChangeLog::new();
        let e = log.record(7, 42);
        assert_eq!(e.epoch_end, 7);
        assert_eq!(e.peer_count, 42);
    }

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipTopologyChangeLog::new();
        let e = log.record(1, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipTopologyChangeLog::new();
        let e = log.record(1, 10);
        assert_eq!(e.prev_hash, GOSSIP_TOPOLOGY_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipTopologyChangeLog::new();
        log.record(1, 10);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 12);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipTopologyChangeLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipTopologyChangeLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 3); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipTopologyChangeLog::new();
        log.record(1, 10);
        log.record(2, 12);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipTopologyChangeLog::new();
        let mut l2 = GossipTopologyChangeLog::new();
        let h1 = l1.record(5, 15).entry_hash;
        let h2 = l2.record(5, 15).entry_hash;
        assert_eq!(h1, h2);
    }
}
