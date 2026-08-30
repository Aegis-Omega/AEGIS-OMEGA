//! Gate 378 — Gossip Fanout Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks how widely each epoch's gossip broadcast has spread across the
//! registered peer network. Records per-epoch fanout metrics in a
//! hash-chained FanoutLog.
//!
//! GossipFanoutEntry (per epoch):
//!   epoch_end:      u64
//!   total_peers:    u32   — peers in registry at time of fanout
//!   reached_peers:  u32   — peers confirmed to have received the frame
//!   coverage_pct:   u32   — floor(reached_peers * 100 / max(total_peers, 1))
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ total_peers_be4
//!                        ‖ reached_peers_be4 ‖ coverage_pct_be4)
//!
//! GossipFanoutLog: record(epoch_end, total_peers, reached_peers),
//!   latest(), entry_count(), full_coverage_count(),
//!   average_coverage_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_FANOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipFanoutEntry ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFanoutEntry {
    pub epoch_end:     u64,
    pub total_peers:   u32,
    pub reached_peers: u32,
    pub coverage_pct:  u32,
    pub entry_hash:    [u8; 32],
    pub prev_hash:     [u8; 32],
}

fn compute_fanout_hash(
    prev:          &[u8; 32],
    epoch_end:     u64,
    total_peers:   u32,
    reached_peers: u32,
    coverage_pct:  u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(reached_peers.to_be_bytes());
    h.update(coverage_pct.to_be_bytes());
    h.finalize().into()
}

// ─── GossipFanoutLog ──────────────────────────────────────────────────────────

pub struct GossipFanoutLog {
    entries: Vec<GossipFanoutEntry>,
}

impl GossipFanoutLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipFanoutEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipFanoutEntry> { self.entries.last() }

    /// Number of epochs where 100% coverage was achieved.
    pub fn full_coverage_count(&self) -> usize {
        self.entries.iter().filter(|e| e.coverage_pct == 100).count()
    }

    /// Integer average coverage percentage across all epochs (floor).
    /// Returns 0 if no entries.
    pub fn average_coverage_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.coverage_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record fanout metrics for one epoch.
    /// coverage_pct = floor(reached_peers * 100 / max(total_peers, 1))
    pub fn record(
        &mut self,
        epoch_end:     u64,
        total_peers:   u32,
        reached_peers: u32,
    ) -> &GossipFanoutEntry {
        let coverage_pct = if total_peers == 0 {
            0
        } else {
            (reached_peers as u64 * 100 / total_peers as u64) as u32
        };

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_FANOUT_GENESIS_HASH);

        let entry_hash = compute_fanout_hash(&prev, epoch_end, total_peers, reached_peers, coverage_pct);

        self.entries.push(GossipFanoutEntry {
            epoch_end,
            total_peers,
            reached_peers,
            coverage_pct,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_FANOUT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_fanout_hash(
                &prev, e.epoch_end, e.total_peers, e.reached_peers, e.coverage_pct,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFanoutLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── coverage_pct calculation ──────────────────────────────────────────────

    #[test]
    fn coverage_pct_full() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(1, 10, 10);
        assert_eq!(e.coverage_pct, 100);
    }

    #[test]
    fn coverage_pct_half() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(1, 10, 5);
        assert_eq!(e.coverage_pct, 50);
    }

    #[test]
    fn coverage_pct_zero_peers() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.coverage_pct, 0);
    }

    #[test]
    fn coverage_pct_floor() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(1, 3, 1); // 1/3 * 100 = 33.33 → floor = 33
        assert_eq!(e.coverage_pct, 33);
    }

    // ── record ────────────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(7, 20, 15);
        assert_eq!(e.epoch_end, 7);
        assert_eq!(e.total_peers, 20);
        assert_eq!(e.reached_peers, 15);
        assert_eq!(e.coverage_pct, 75);
    }

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(1, 5, 5);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(1, 5, 5);
        assert_eq!(e.prev_hash, GOSSIP_FANOUT_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipFanoutLog::new();
        log.record(1, 5, 5);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 5, 4);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn full_coverage_count() {
        let mut log = GossipFanoutLog::new();
        log.record(1, 10, 10); // 100%
        log.record(2, 10,  8); //  80%
        log.record(3, 10, 10); // 100%
        assert_eq!(log.full_coverage_count(), 2);
    }

    #[test]
    fn average_coverage_pct_empty() {
        let log = GossipFanoutLog::new();
        assert_eq!(log.average_coverage_pct(), 0);
    }

    #[test]
    fn average_coverage_pct_computed() {
        let mut log = GossipFanoutLog::new();
        log.record(1, 10, 10); // 100
        log.record(2, 10,  0); //   0
        assert_eq!(log.average_coverage_pct(), 50);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipFanoutLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_entries_ok() {
        let mut log = GossipFanoutLog::new();
        for i in 1u64..=4 { log.record(i, 10, i as u32); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipFanoutLog::new();
        log.record(1, 5, 5);
        log.record(2, 5, 4);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipFanoutLog::new();
        let mut l2 = GossipFanoutLog::new();
        let h1 = l1.record(9, 8, 6).entry_hash;
        let h2 = l2.record(9, 8, 6).entry_hash;
        assert_eq!(h1, h2);
    }
}
