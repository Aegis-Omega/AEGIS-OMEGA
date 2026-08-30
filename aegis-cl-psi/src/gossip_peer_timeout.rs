//! Gate 407 — Gossip Peer Timeout Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of peer connection timeout events.
//!
//! timeout_count:    u32 — number of peer timeouts this epoch
//! active_peers:     u32 — peers active at epoch start
//! timeout_rate_pct: u32 — timeout_count * 100 / max(active_peers, 1)
//! high_timeout:     bool — timeout_rate_pct >= TIMEOUT_RATE_THRESHOLD (10%)
//!
//! TIMEOUT_RATE_THRESHOLD: u32 = 10
//!
//! GossipPeerTimeoutEntry (hash-chained):
//!   epoch_end:        u64
//!   timeout_count:    u32
//!   active_peers:     u32
//!   timeout_rate_pct: u32
//!   high_timeout:     bool
//!   entry_hash:       [u8;32]
//!   prev_hash:        [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ timeout_count_be4
//!                       ‖ active_peers_be4 ‖ timeout_rate_pct_be4 ‖ high_timeout_byte)
//!
//! GossipPeerTimeoutLog: record(epoch_end, timeout_count, active_peers),
//!   total_timeouts(), high_timeout_count(), max_timeout_rate_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_PEER_TIMEOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const TIMEOUT_RATE_THRESHOLD: u32 = 10; // percent

// ─── GossipPeerTimeoutEntry ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerTimeoutEntry {
    pub epoch_end:        u64,
    pub timeout_count:    u32,
    pub active_peers:     u32,
    pub timeout_rate_pct: u32,
    pub high_timeout:     bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_peer_timeout_hash(
    prev:             &[u8; 32],
    epoch_end:        u64,
    timeout_count:    u32,
    active_peers:     u32,
    timeout_rate_pct: u32,
    high_timeout:     bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(timeout_count.to_be_bytes());
    h.update(active_peers.to_be_bytes());
    h.update(timeout_rate_pct.to_be_bytes());
    h.update([high_timeout as u8]);
    h.finalize().into()
}

// ─── GossipPeerTimeoutLog ─────────────────────────────────────────────────────

pub struct GossipPeerTimeoutLog {
    entries: Vec<GossipPeerTimeoutEntry>,
}

impl GossipPeerTimeoutLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipPeerTimeoutEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipPeerTimeoutEntry> { self.entries.last() }

    /// Total timeout events across all epochs.
    pub fn total_timeouts(&self) -> u64 {
        self.entries.iter().map(|e| e.timeout_count as u64).sum()
    }

    /// Count of epochs where high_timeout == true.
    pub fn high_timeout_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_timeout).count()
    }

    /// Maximum timeout_rate_pct in any epoch. Returns 0 if empty.
    pub fn max_timeout_rate_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.timeout_rate_pct).max().unwrap_or(0)
    }

    /// Record timeout stats for one epoch.
    /// timeout_rate_pct = timeout_count * 100 / max(active_peers, 1).
    /// high_timeout = timeout_rate_pct >= TIMEOUT_RATE_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:     u64,
        timeout_count: u32,
        active_peers:  u32,
    ) -> &GossipPeerTimeoutEntry {
        let timeout_rate_pct = (timeout_count as u64 * 100
            / active_peers.max(1) as u64) as u32;
        let high_timeout = timeout_rate_pct >= TIMEOUT_RATE_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PEER_TIMEOUT_GENESIS_HASH);

        let entry_hash = compute_peer_timeout_hash(
            &prev, epoch_end, timeout_count, active_peers, timeout_rate_pct, high_timeout,
        );

        self.entries.push(GossipPeerTimeoutEntry {
            epoch_end,
            timeout_count,
            active_peers,
            timeout_rate_pct,
            high_timeout,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PEER_TIMEOUT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_peer_timeout_hash(
                &prev, e.epoch_end, e.timeout_count, e.active_peers,
                e.timeout_rate_pct, e.high_timeout,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerTimeoutLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(1, 5, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.timeout_count, 5);
        assert_eq!(e.active_peers, 100);
        assert_eq!(e.timeout_rate_pct, 5);
    }

    #[test]
    fn zero_peers_stored() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.timeout_rate_pct, 0);
        assert!(!e.high_timeout);
    }

    #[test]
    fn rate_rounds_down() {
        let mut log = GossipPeerTimeoutLog::new();
        // 15 * 100 / 101 = 14 (rounds down)
        let e = log.record(1, 15, 101);
        assert_eq!(e.timeout_rate_pct, 14);
    }

    // ── high_timeout threshold ────────────────────────────────────────────────

    #[test]
    fn high_timeout_below_threshold() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(1, 9, 100);
        assert_eq!(e.timeout_rate_pct, 9);
        assert!(!e.high_timeout);
    }

    #[test]
    fn high_timeout_at_threshold() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(1, 10, 100);
        assert_eq!(e.timeout_rate_pct, 10);
        assert!(e.high_timeout);
    }

    #[test]
    fn high_timeout_above_threshold() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(1, 25, 100);
        assert!(e.high_timeout);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(1, 5, 100);
        log.record(2, 3, 100);
        log.record(3, 7, 100);
        assert_eq!(log.total_timeouts(), 15);
    }

    #[test]
    fn high_timeout_count_correct() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(1, 5, 100);  // 5% — ok
        log.record(2, 10, 100); // 10% — high
        log.record(3, 20, 100); // 20% — high
        log.record(4, 9, 100);  // 9% — ok
        assert_eq!(log.high_timeout_count(), 2);
    }

    #[test]
    fn max_timeout_rate_pct_correct() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(1, 5, 100);
        log.record(2, 25, 100);
        log.record(3, 15, 100);
        assert_eq!(log.max_timeout_rate_pct(), 25);
    }

    #[test]
    fn max_timeout_rate_empty_zero() {
        let log = GossipPeerTimeoutLog::new();
        assert_eq!(log.max_timeout_rate_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(1, 5, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(1, 5, 100);
        assert_eq!(e.prev_hash, GOSSIP_PEER_TIMEOUT_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(1, 5, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 3, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPeerTimeoutLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPeerTimeoutLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 2, 100); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(1, 5, 100);
        log.record(2, 3, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipPeerTimeoutLog::new();
        let mut l2 = GossipPeerTimeoutLog::new();
        let h1 = l1.record(7, 12, 150).entry_hash;
        let h2 = l2.record(7, 12, 150).entry_hash;
        assert_eq!(h1, h2);
    }
}
