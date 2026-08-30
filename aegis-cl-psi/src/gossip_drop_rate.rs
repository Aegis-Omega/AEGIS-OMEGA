//! Gate 385 — Gossip Drop Rate Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks the per-epoch frame drop rate — the fraction of dispatched frames
//! that were not successfully delivered. Represented as an integer percentage
//! (floor division, no f64).
//!
//! GossipDropRateEntry (hash-chained):
//!   epoch_end:      u64
//!   dispatched:     u32   — total frames dispatched this epoch
//!   dropped:        u32   — frames not delivered (dispatched - delivered)
//!   drop_pct:       u32   — floor(dropped * 100 / max(dispatched, 1))
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ dispatched_be4
//!                        ‖ dropped_be4 ‖ drop_pct_be4)
//!
//! GossipDropRateLog: record(epoch_end, dispatched, delivered),
//!   latest(), entry_count(), high_drop_count(threshold_pct),
//!   average_drop_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_DROP_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipDropRateEntry ──────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDropRateEntry {
    pub epoch_end:  u64,
    pub dispatched: u32,
    pub dropped:    u32,
    pub drop_pct:   u32,
    pub entry_hash: [u8; 32],
    pub prev_hash:  [u8; 32],
}

fn compute_drop_hash(
    prev:       &[u8; 32],
    epoch_end:  u64,
    dispatched: u32,
    dropped:    u32,
    drop_pct:   u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(dispatched.to_be_bytes());
    h.update(dropped.to_be_bytes());
    h.update(drop_pct.to_be_bytes());
    h.finalize().into()
}

// ─── GossipDropRateLog ────────────────────────────────────────────────────────

pub struct GossipDropRateLog {
    entries: Vec<GossipDropRateEntry>,
}

impl GossipDropRateLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipDropRateEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipDropRateEntry> { self.entries.last() }

    /// Count of epochs where drop_pct >= threshold_pct.
    pub fn high_drop_count(&self, threshold_pct: u32) -> usize {
        self.entries.iter().filter(|e| e.drop_pct >= threshold_pct).count()
    }

    /// Integer average drop_pct across all epochs (floor). Returns 0 if empty.
    pub fn average_drop_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.drop_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record drop stats for one epoch.
    /// dropped = dispatched.saturating_sub(delivered) (never negative).
    /// drop_pct = floor(dropped * 100 / max(dispatched, 1)).
    pub fn record(
        &mut self,
        epoch_end:  u64,
        dispatched: u32,
        delivered:  u32,
    ) -> &GossipDropRateEntry {
        let dropped = dispatched.saturating_sub(delivered);
        let drop_pct = if dispatched == 0 {
            0
        } else {
            (dropped as u64 * 100 / dispatched as u64) as u32
        };

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_DROP_GENESIS_HASH);

        let entry_hash = compute_drop_hash(&prev, epoch_end, dispatched, dropped, drop_pct);

        self.entries.push(GossipDropRateEntry {
            epoch_end,
            dispatched,
            dropped,
            drop_pct,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_DROP_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_drop_hash(
                &prev, e.epoch_end, e.dispatched, e.dropped, e.drop_pct,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipDropRateLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── drop calculation ──────────────────────────────────────────────────────

    #[test]
    fn drop_pct_zero_when_all_delivered() {
        let mut log = GossipDropRateLog::new();
        let e = log.record(1, 10, 10);
        assert_eq!(e.dropped, 0);
        assert_eq!(e.drop_pct, 0);
    }

    #[test]
    fn drop_pct_100_when_none_delivered() {
        let mut log = GossipDropRateLog::new();
        let e = log.record(1, 10, 0);
        assert_eq!(e.dropped, 10);
        assert_eq!(e.drop_pct, 100);
    }

    #[test]
    fn drop_pct_half() {
        let mut log = GossipDropRateLog::new();
        let e = log.record(1, 10, 5);
        assert_eq!(e.dropped, 5);
        assert_eq!(e.drop_pct, 50);
    }

    #[test]
    fn drop_pct_floor() {
        let mut log = GossipDropRateLog::new();
        // dispatched=3, delivered=2, dropped=1 → 1/3*100 = 33.33 → floor=33
        let e = log.record(1, 3, 2);
        assert_eq!(e.drop_pct, 33);
    }

    #[test]
    fn zero_dispatched_drop_pct_zero() {
        let mut log = GossipDropRateLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.drop_pct, 0);
        assert_eq!(e.dropped, 0);
    }

    #[test]
    fn delivered_exceeds_dispatched_dropped_is_zero() {
        // saturating_sub protects against underflow
        let mut log = GossipDropRateLog::new();
        let e = log.record(1, 5, 10);
        assert_eq!(e.dropped, 0);
        assert_eq!(e.drop_pct, 0);
    }

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipDropRateLog::new();
        let e = log.record(7, 20, 15);
        assert_eq!(e.epoch_end, 7);
        assert_eq!(e.dispatched, 20);
        assert_eq!(e.dropped, 5);
        assert_eq!(e.drop_pct, 25);
    }

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipDropRateLog::new();
        let e = log.record(1, 10, 8);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipDropRateLog::new();
        let e = log.record(1, 10, 8);
        assert_eq!(e.prev_hash, GOSSIP_DROP_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipDropRateLog::new();
        log.record(1, 10, 8);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 10, 9);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn high_drop_count_threshold() {
        let mut log = GossipDropRateLog::new();
        log.record(1, 10, 9);  // drop_pct=10
        log.record(2, 10, 5);  // drop_pct=50
        log.record(3, 10, 0);  // drop_pct=100
        assert_eq!(log.high_drop_count(50), 2); // pct >= 50
        assert_eq!(log.high_drop_count(100), 1);
        assert_eq!(log.high_drop_count(0), 3);
    }

    #[test]
    fn average_drop_pct_empty_zero() {
        let log = GossipDropRateLog::new();
        assert_eq!(log.average_drop_pct(), 0);
    }

    #[test]
    fn average_drop_pct_floor() {
        let mut log = GossipDropRateLog::new();
        log.record(1, 10, 7); // drop_pct=30
        log.record(2, 10, 6); // drop_pct=40
        // avg = floor(70/2) = 35
        assert_eq!(log.average_drop_pct(), 35);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipDropRateLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipDropRateLog::new();
        for i in 1u64..=5 { log.record(i, 10, i as u32); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipDropRateLog::new();
        log.record(1, 10, 8);
        log.record(2, 10, 7);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipDropRateLog::new();
        let mut l2 = GossipDropRateLog::new();
        let h1 = l1.record(9, 8, 6).entry_hash;
        let h2 = l2.record(9, 8, 6).entry_hash;
        assert_eq!(h1, h2);
    }
}
