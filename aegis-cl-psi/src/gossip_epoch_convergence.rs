//! Gate 413 — Gossip Epoch Convergence Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip state convergence across peers.
//! Convergence measures how many peers share the same view of the current state.
//!
//! peers_total:       u32 — total peers this epoch
//! peers_converged:   u32 — peers that share the canonical state hash
//! convergence_pct:   u32 — peers_converged * 100 / max(peers_total, 1)
//! not_converged:     bool — convergence_pct < CONVERGENCE_FLOOR (75%)
//!
//! CONVERGENCE_FLOOR: u32 = 75
//!
//! GossipEpochConvergenceEntry (hash-chained):
//!   epoch_end:       u64
//!   peers_total:     u32
//!   peers_converged: u32
//!   convergence_pct: u32
//!   not_converged:   bool
//!   entry_hash:      [u8;32]
//!   prev_hash:       [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ peers_total_be4
//!                       ‖ peers_converged_be4 ‖ convergence_pct_be4
//!                       ‖ not_converged_byte)
//!
//! GossipEpochConvergenceLog: record(epoch_end, peers_total, peers_converged),
//!   not_converged_count(), min_convergence_pct(), mean_convergence_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_EPOCH_CONVERGENCE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const CONVERGENCE_FLOOR: u32 = 75; // percent

// ─── GossipEpochConvergenceEntry ──────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochConvergenceEntry {
    pub epoch_end:       u64,
    pub peers_total:     u32,
    pub peers_converged: u32,
    pub convergence_pct: u32,
    pub not_converged:   bool,
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_epoch_convergence_hash(
    prev:            &[u8; 32],
    epoch_end:       u64,
    peers_total:     u32,
    peers_converged: u32,
    convergence_pct: u32,
    not_converged:   bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(peers_total.to_be_bytes());
    h.update(peers_converged.to_be_bytes());
    h.update(convergence_pct.to_be_bytes());
    h.update([not_converged as u8]);
    h.finalize().into()
}

// ─── GossipEpochConvergenceLog ────────────────────────────────────────────────

pub struct GossipEpochConvergenceLog {
    entries: Vec<GossipEpochConvergenceEntry>,
}

impl GossipEpochConvergenceLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipEpochConvergenceEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipEpochConvergenceEntry> { self.entries.last() }

    /// Count of epochs where not_converged == true.
    pub fn not_converged_count(&self) -> usize {
        self.entries.iter().filter(|e| e.not_converged).count()
    }

    /// Minimum convergence_pct across all epochs. Returns 100 if empty.
    pub fn min_convergence_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.convergence_pct).min().unwrap_or(100)
    }

    /// Integer mean of all per-epoch convergence_pct values. Returns 0 if empty.
    pub fn mean_convergence_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.convergence_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record convergence stats for one epoch.
    /// convergence_pct = peers_converged * 100 / max(peers_total, 1).
    /// not_converged = convergence_pct < CONVERGENCE_FLOOR.
    pub fn record(
        &mut self,
        epoch_end:       u64,
        peers_total:     u32,
        peers_converged: u32,
    ) -> &GossipEpochConvergenceEntry {
        let convergence_pct = (peers_converged as u64 * 100
            / peers_total.max(1) as u64) as u32;
        let not_converged = convergence_pct < CONVERGENCE_FLOOR;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_EPOCH_CONVERGENCE_GENESIS_HASH);

        let entry_hash = compute_epoch_convergence_hash(
            &prev, epoch_end, peers_total, peers_converged,
            convergence_pct, not_converged,
        );

        self.entries.push(GossipEpochConvergenceEntry {
            epoch_end,
            peers_total,
            peers_converged,
            convergence_pct,
            not_converged,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_EPOCH_CONVERGENCE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_epoch_convergence_hash(
                &prev, e.epoch_end, e.peers_total, e.peers_converged,
                e.convergence_pct, e.not_converged,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochConvergenceLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipEpochConvergenceLog::new();
        let e = log.record(1, 100, 80);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.peers_total, 100);
        assert_eq!(e.peers_converged, 80);
        assert_eq!(e.convergence_pct, 80);
    }

    #[test]
    fn zero_peers_stored() {
        let mut log = GossipEpochConvergenceLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.convergence_pct, 0);
        assert!(e.not_converged);
    }

    #[test]
    fn full_convergence() {
        let mut log = GossipEpochConvergenceLog::new();
        let e = log.record(1, 100, 100);
        assert_eq!(e.convergence_pct, 100);
        assert!(!e.not_converged);
    }

    #[test]
    fn convergence_rounds_down() {
        let mut log = GossipEpochConvergenceLog::new();
        // 76*100/101 = 75 (rounds down)
        let e = log.record(1, 101, 76);
        assert_eq!(e.convergence_pct, 75);
    }

    // ── not_converged threshold ───────────────────────────────────────────────

    #[test]
    fn not_converged_below_floor() {
        let mut log = GossipEpochConvergenceLog::new();
        let e = log.record(1, 100, 74);
        assert_eq!(e.convergence_pct, 74);
        assert!(e.not_converged);
    }

    #[test]
    fn converged_at_floor() {
        let mut log = GossipEpochConvergenceLog::new();
        let e = log.record(1, 100, 75);
        assert_eq!(e.convergence_pct, 75);
        assert!(!e.not_converged);
    }

    #[test]
    fn converged_above_floor() {
        let mut log = GossipEpochConvergenceLog::new();
        let e = log.record(1, 100, 95);
        assert!(!e.not_converged);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn not_converged_count_correct() {
        let mut log = GossipEpochConvergenceLog::new();
        log.record(1, 100, 80); // 80% — ok
        log.record(2, 100, 70); // 70% — not converged
        log.record(3, 100, 75); // 75% — ok (at floor)
        log.record(4, 100, 60); // 60% — not converged
        assert_eq!(log.not_converged_count(), 2);
    }

    #[test]
    fn min_convergence_pct_correct() {
        let mut log = GossipEpochConvergenceLog::new();
        log.record(1, 100, 90);
        log.record(2, 100, 65);
        log.record(3, 100, 85);
        assert_eq!(log.min_convergence_pct(), 65);
    }

    #[test]
    fn min_convergence_empty_is_100() {
        let log = GossipEpochConvergenceLog::new();
        assert_eq!(log.min_convergence_pct(), 100);
    }

    #[test]
    fn mean_convergence_pct_correct() {
        let mut log = GossipEpochConvergenceLog::new();
        log.record(1, 100, 80); // 80%
        log.record(2, 100, 60); // 60%
        log.record(3, 100, 70); // 70%
        // (80+60+70)/3 = 70
        assert_eq!(log.mean_convergence_pct(), 70);
    }

    #[test]
    fn mean_convergence_empty_zero() {
        let log = GossipEpochConvergenceLog::new();
        assert_eq!(log.mean_convergence_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipEpochConvergenceLog::new();
        let e = log.record(1, 100, 80);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipEpochConvergenceLog::new();
        let e = log.record(1, 100, 80);
        assert_eq!(e.prev_hash, GOSSIP_EPOCH_CONVERGENCE_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipEpochConvergenceLog::new();
        log.record(1, 100, 80);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 100, 90);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipEpochConvergenceLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipEpochConvergenceLog::new();
        for i in 1u64..=5 { log.record(i, 100, i as u32 * 18); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipEpochConvergenceLog::new();
        log.record(1, 100, 80);
        log.record(2, 100, 90);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipEpochConvergenceLog::new();
        let mut l2 = GossipEpochConvergenceLog::new();
        let h1 = l1.record(3, 100, 85).entry_hash;
        let h2 = l2.record(3, 100, 85).entry_hash;
        assert_eq!(h1, h2);
    }
}
