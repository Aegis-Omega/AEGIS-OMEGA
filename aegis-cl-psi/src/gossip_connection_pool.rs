//! Gate 409 — Gossip Connection Pool Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of the gossip connection pool state.
//!
//! pool_size:      u32 — total connections in pool at epoch end
//! active_count:   u32 — connections actively sending/receiving (≤ pool_size)
//! idle_count:     u32 — pool_size - active_count
//! utilization_pct: u32 — active_count * 100 / max(pool_size, 1)
//! underutilized:  bool — utilization_pct < POOL_UTILIZATION_FLOOR (30%)
//!
//! POOL_UTILIZATION_FLOOR: u32 = 30
//!
//! GossipConnectionPoolEntry (hash-chained):
//!   epoch_end:        u64
//!   pool_size:        u32
//!   active_count:     u32
//!   idle_count:       u32
//!   utilization_pct:  u32
//!   underutilized:    bool
//!   entry_hash:       [u8;32]
//!   prev_hash:        [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ pool_size_be4
//!                       ‖ active_count_be4 ‖ idle_count_be4
//!                       ‖ utilization_pct_be4 ‖ underutilized_byte)
//!
//! GossipConnectionPoolLog: record(epoch_end, pool_size, active_count),
//!   max_pool_size(), underutilized_count(), min_utilization_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_CONNECTION_POOL_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const POOL_UTILIZATION_FLOOR: u32 = 30; // percent

// ─── GossipConnectionPoolEntry ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipConnectionPoolEntry {
    pub epoch_end:       u64,
    pub pool_size:       u32,
    pub active_count:    u32,
    pub idle_count:      u32,
    pub utilization_pct: u32,
    pub underutilized:   bool,
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_connection_pool_hash(
    prev:            &[u8; 32],
    epoch_end:       u64,
    pool_size:       u32,
    active_count:    u32,
    idle_count:      u32,
    utilization_pct: u32,
    underutilized:   bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(pool_size.to_be_bytes());
    h.update(active_count.to_be_bytes());
    h.update(idle_count.to_be_bytes());
    h.update(utilization_pct.to_be_bytes());
    h.update([underutilized as u8]);
    h.finalize().into()
}

// ─── GossipConnectionPoolLog ──────────────────────────────────────────────────

pub struct GossipConnectionPoolLog {
    entries: Vec<GossipConnectionPoolEntry>,
}

impl GossipConnectionPoolLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipConnectionPoolEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipConnectionPoolEntry> { self.entries.last() }

    /// Maximum pool_size ever seen. Returns 0 if empty.
    pub fn max_pool_size(&self) -> u32 {
        self.entries.iter().map(|e| e.pool_size).max().unwrap_or(0)
    }

    /// Count of epochs where underutilized == true.
    pub fn underutilized_count(&self) -> usize {
        self.entries.iter().filter(|e| e.underutilized).count()
    }

    /// Minimum utilization_pct across all epochs. Returns 100 if empty.
    pub fn min_utilization_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.utilization_pct).min().unwrap_or(100)
    }

    /// Record connection pool state for one epoch.
    /// idle_count = pool_size.saturating_sub(active_count).
    /// utilization_pct = active_count * 100 / max(pool_size, 1).
    /// underutilized = utilization_pct < POOL_UTILIZATION_FLOOR.
    pub fn record(
        &mut self,
        epoch_end:    u64,
        pool_size:    u32,
        active_count: u32,
    ) -> &GossipConnectionPoolEntry {
        let idle_count = pool_size.saturating_sub(active_count);
        let utilization_pct = (active_count as u64 * 100
            / pool_size.max(1) as u64) as u32;
        let underutilized = utilization_pct < POOL_UTILIZATION_FLOOR;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_CONNECTION_POOL_GENESIS_HASH);

        let entry_hash = compute_connection_pool_hash(
            &prev, epoch_end, pool_size, active_count, idle_count,
            utilization_pct, underutilized,
        );

        self.entries.push(GossipConnectionPoolEntry {
            epoch_end,
            pool_size,
            active_count,
            idle_count,
            utilization_pct,
            underutilized,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_CONNECTION_POOL_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_connection_pool_hash(
                &prev, e.epoch_end, e.pool_size, e.active_count, e.idle_count,
                e.utilization_pct, e.underutilized,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipConnectionPoolLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipConnectionPoolLog::new();
        let e = log.record(1, 100, 60);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.pool_size, 100);
        assert_eq!(e.active_count, 60);
        assert_eq!(e.idle_count, 40);
        assert_eq!(e.utilization_pct, 60);
    }

    #[test]
    fn zero_pool_stored() {
        let mut log = GossipConnectionPoolLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.utilization_pct, 0);
        assert!(e.underutilized);
    }

    #[test]
    fn full_utilization() {
        let mut log = GossipConnectionPoolLog::new();
        let e = log.record(1, 100, 100);
        assert_eq!(e.idle_count, 0);
        assert_eq!(e.utilization_pct, 100);
        assert!(!e.underutilized);
    }

    #[test]
    fn active_capped_at_pool_size() {
        let mut log = GossipConnectionPoolLog::new();
        // active > pool_size: idle saturates to 0
        let e = log.record(1, 50, 80);
        assert_eq!(e.idle_count, 0);
    }

    #[test]
    fn utilization_rounds_down() {
        let mut log = GossipConnectionPoolLog::new();
        // 31*100/101 = 30 (rounds down)
        let e = log.record(1, 101, 31);
        assert_eq!(e.utilization_pct, 30);
    }

    // ── underutilized threshold ───────────────────────────────────────────────

    #[test]
    fn underutilized_below_floor() {
        let mut log = GossipConnectionPoolLog::new();
        let e = log.record(1, 100, 29);
        assert_eq!(e.utilization_pct, 29);
        assert!(e.underutilized);
    }

    #[test]
    fn utilization_at_floor_not_underutilized() {
        let mut log = GossipConnectionPoolLog::new();
        let e = log.record(1, 100, 30);
        assert_eq!(e.utilization_pct, 30);
        assert!(!e.underutilized);
    }

    #[test]
    fn high_utilization_not_underutilized() {
        let mut log = GossipConnectionPoolLog::new();
        let e = log.record(1, 100, 75);
        assert!(!e.underutilized);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn max_pool_size_correct() {
        let mut log = GossipConnectionPoolLog::new();
        log.record(1, 100, 50);
        log.record(2, 200, 100);
        log.record(3, 150, 80);
        assert_eq!(log.max_pool_size(), 200);
    }

    #[test]
    fn max_pool_size_empty_zero() {
        let log = GossipConnectionPoolLog::new();
        assert_eq!(log.max_pool_size(), 0);
    }

    #[test]
    fn underutilized_count_correct() {
        let mut log = GossipConnectionPoolLog::new();
        log.record(1, 100, 50); // 50% — ok
        log.record(2, 100, 20); // 20% — under
        log.record(3, 100, 30); // 30% — ok (at floor)
        log.record(4, 100, 10); // 10% — under
        assert_eq!(log.underutilized_count(), 2);
    }

    #[test]
    fn min_utilization_pct_correct() {
        let mut log = GossipConnectionPoolLog::new();
        log.record(1, 100, 90);
        log.record(2, 100, 25);
        log.record(3, 100, 60);
        assert_eq!(log.min_utilization_pct(), 25);
    }

    #[test]
    fn min_utilization_empty_is_100() {
        let log = GossipConnectionPoolLog::new();
        assert_eq!(log.min_utilization_pct(), 100);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipConnectionPoolLog::new();
        let e = log.record(1, 100, 60);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipConnectionPoolLog::new();
        let e = log.record(1, 100, 60);
        assert_eq!(e.prev_hash, GOSSIP_CONNECTION_POOL_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipConnectionPoolLog::new();
        log.record(1, 100, 60);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 120, 70);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipConnectionPoolLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipConnectionPoolLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 20, i as u32 * 12); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipConnectionPoolLog::new();
        log.record(1, 100, 60);
        log.record(2, 120, 70);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipConnectionPoolLog::new();
        let mut l2 = GossipConnectionPoolLog::new();
        let h1 = l1.record(4, 80, 55).entry_hash;
        let h2 = l2.record(4, 80, 55).entry_hash;
        assert_eq!(h1, h2);
    }
}
