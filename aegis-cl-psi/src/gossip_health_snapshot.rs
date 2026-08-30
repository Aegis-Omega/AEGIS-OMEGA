//! Gate 381 — Gossip Health Snapshot (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Aggregates per-epoch gossip health signals from the fanout tracker,
//! latency tracker, and epoch window into a single hash-chained snapshot.
//!
//! GossipHealthSnapshot (hash-chained):
//!   epoch_end:         u64
//!   coverage_pct:      u32   — fanout coverage for this epoch
//!   avg_latency:       u64   — average latency_epochs across all peers
//!   window_avg_pct:    u32   — rolling-window average coverage (last ≤4 epochs)
//!   window_state:      u8    — GossipWindowState: 0=Healthy 1=Degraded 2=Critical
//!   snapshot_hash:     [u8;32]
//!   prev_hash:         [u8;32]
//!
//! snapshot_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ coverage_pct_be4
//!                           ‖ avg_latency_be8 ‖ window_avg_pct_be4 ‖ window_state_byte)
//!
//! GossipHealthLog: record(epoch_end, coverage_pct, avg_latency, window_avg_pct, window_state),
//!   latest(), snapshot_count(), healthy_count(), degraded_count(), critical_count(),
//!   verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_SNAPSHOT_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipHealthSnapshot ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipHealthSnapshot {
    pub epoch_end:      u64,
    pub coverage_pct:   u32,
    pub avg_latency:    u64,
    pub window_avg_pct: u32,
    pub window_state:   u8,
    pub snapshot_hash:  [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_snapshot_hash(
    prev:           &[u8; 32],
    epoch_end:      u64,
    coverage_pct:   u32,
    avg_latency:    u64,
    window_avg_pct: u32,
    window_state:   u8,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(coverage_pct.to_be_bytes());
    h.update(avg_latency.to_be_bytes());
    h.update(window_avg_pct.to_be_bytes());
    h.update([window_state]);
    h.finalize().into()
}

// ─── GossipHealthLog ──────────────────────────────────────────────────────────

pub struct GossipHealthLog {
    snapshots: Vec<GossipHealthSnapshot>,
}

impl GossipHealthLog {
    pub fn new() -> Self { Self { snapshots: Vec::new() } }

    pub fn snapshot_count(&self) -> usize { self.snapshots.len() }
    pub fn is_empty(&self)        -> bool  { self.snapshots.is_empty() }
    pub fn snapshots(&self)       -> &[GossipHealthSnapshot] { &self.snapshots }
    pub fn latest(&self)          -> Option<&GossipHealthSnapshot> { self.snapshots.last() }

    pub fn healthy_count(&self) -> usize {
        self.snapshots.iter().filter(|s| s.window_state == 0).count()
    }

    pub fn degraded_count(&self) -> usize {
        self.snapshots.iter().filter(|s| s.window_state == 1).count()
    }

    pub fn critical_count(&self) -> usize {
        self.snapshots.iter().filter(|s| s.window_state == 2).count()
    }

    /// Record a health snapshot for one epoch.
    pub fn record(
        &mut self,
        epoch_end:      u64,
        coverage_pct:   u32,
        avg_latency:    u64,
        window_avg_pct: u32,
        window_state:   u8,
    ) -> &GossipHealthSnapshot {
        let prev = self.snapshots.last()
            .map(|s| s.snapshot_hash)
            .unwrap_or(GOSSIP_SNAPSHOT_GENESIS_HASH);

        let snapshot_hash = compute_snapshot_hash(
            &prev, epoch_end, coverage_pct, avg_latency, window_avg_pct, window_state,
        );

        self.snapshots.push(GossipHealthSnapshot {
            epoch_end,
            coverage_pct,
            avg_latency,
            window_avg_pct,
            window_state,
            snapshot_hash,
            prev_hash: prev,
        });
        self.snapshots.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_SNAPSHOT_GENESIS_HASH;
        for (i, s) in self.snapshots.iter().enumerate() {
            if s.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_snapshot_hash(
                &prev,
                s.epoch_end,
                s.coverage_pct,
                s.avg_latency,
                s.window_avg_pct,
                s.window_state,
            );
            if s.snapshot_hash != expected {
                return (false, Some(i));
            }
            prev = s.snapshot_hash;
        }
        (true, None)
    }
}

impl Default for GossipHealthLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record ────────────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipHealthLog::new();
        let s = log.record(5, 80, 3, 75, 0);
        assert_eq!(s.epoch_end, 5);
        assert_eq!(s.coverage_pct, 80);
        assert_eq!(s.avg_latency, 3);
        assert_eq!(s.window_avg_pct, 75);
        assert_eq!(s.window_state, 0);
    }

    #[test]
    fn snapshot_hash_nonzero() {
        let mut log = GossipHealthLog::new();
        let s = log.record(1, 80, 2, 80, 0);
        assert_ne!(s.snapshot_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_is_genesis() {
        let mut log = GossipHealthLog::new();
        let s = log.record(1, 80, 2, 80, 0);
        assert_eq!(s.prev_hash, GOSSIP_SNAPSHOT_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipHealthLog::new();
        log.record(1, 80, 2, 80, 0);
        let h0 = log.snapshots()[0].snapshot_hash;
        log.record(2, 70, 3, 75, 0);
        assert_eq!(log.snapshots()[1].prev_hash, h0);
    }

    #[test]
    fn snapshot_count_increments() {
        let mut log = GossipHealthLog::new();
        assert_eq!(log.snapshot_count(), 0);
        log.record(1, 80, 1, 80, 0);
        log.record(2, 70, 2, 75, 1);
        assert_eq!(log.snapshot_count(), 2);
    }

    // ── state counts ──────────────────────────────────────────────────────────

    #[test]
    fn healthy_count_correct() {
        let mut log = GossipHealthLog::new();
        log.record(1, 80, 1, 80, 0); // Healthy
        log.record(2, 60, 2, 60, 1); // Degraded
        log.record(3, 30, 3, 40, 2); // Critical
        assert_eq!(log.healthy_count(), 1);
        assert_eq!(log.degraded_count(), 1);
        assert_eq!(log.critical_count(), 1);
    }

    #[test]
    fn all_healthy() {
        let mut log = GossipHealthLog::new();
        for i in 1u64..=4 { log.record(i, 90, 1, 85, 0); }
        assert_eq!(log.healthy_count(), 4);
        assert_eq!(log.degraded_count(), 0);
        assert_eq!(log.critical_count(), 0);
    }

    #[test]
    fn all_critical() {
        let mut log = GossipHealthLog::new();
        for i in 1u64..=3 { log.record(i, 20, 10, 30, 2); }
        assert_eq!(log.critical_count(), 3);
        assert_eq!(log.healthy_count(), 0);
    }

    // ── latest ────────────────────────────────────────────────────────────────

    #[test]
    fn latest_returns_most_recent() {
        let mut log = GossipHealthLog::new();
        log.record(1, 80, 1, 80, 0);
        log.record(2, 60, 2, 70, 1);
        assert_eq!(log.latest().unwrap().epoch_end, 2);
    }

    #[test]
    fn latest_on_empty_returns_none() {
        let log = GossipHealthLog::new();
        assert!(log.latest().is_none());
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipHealthLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipHealthLog::new();
        for i in 1u64..=5 { log.record(i, 80, 2, 80, 0); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipHealthLog::new();
        log.record(1, 80, 1, 80, 0);
        log.record(2, 70, 2, 75, 0);
        log.snapshots[0].snapshot_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn snapshot_hash_deterministic() {
        let mut l1 = GossipHealthLog::new();
        let mut l2 = GossipHealthLog::new();
        let h1 = l1.record(7, 75, 4, 78, 0).snapshot_hash;
        let h2 = l2.record(7, 75, 4, 78, 0).snapshot_hash;
        assert_eq!(h1, h2);
    }

    // ── different fields → different hash ─────────────────────────────────────

    #[test]
    fn different_coverage_gives_different_hash() {
        let mut l1 = GossipHealthLog::new();
        let mut l2 = GossipHealthLog::new();
        let h1 = l1.record(1, 80, 2, 80, 0).snapshot_hash;
        let h2 = l2.record(1, 70, 2, 80, 0).snapshot_hash;
        assert_ne!(h1, h2);
    }

    #[test]
    fn different_latency_gives_different_hash() {
        let mut l1 = GossipHealthLog::new();
        let mut l2 = GossipHealthLog::new();
        let h1 = l1.record(1, 80, 2, 80, 0).snapshot_hash;
        let h2 = l2.record(1, 80, 5, 80, 0).snapshot_hash;
        assert_ne!(h1, h2);
    }
}
