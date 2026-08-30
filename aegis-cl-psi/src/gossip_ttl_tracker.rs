//! Gate 403 — Gossip TTL Tracker Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of message Time-To-Live (TTL) hop counts. Each gossip
//! message carries a TTL that decrements at each hop; a message is dropped
//! when TTL reaches zero.
//!
//! expired_count:   u32 — messages dropped because TTL reached 0
//! delivered_count: u32 — messages that reached a recipient before TTL expired
//! mean_hops_x10:   u32 — (total hops across delivered messages * 10)
//!                         / max(delivered_count, 1) (scaled by 10, integer).
//! ttl_efficiency_pct: u32 — delivered_count * 100 / max(expired + delivered, 1)
//! low_efficiency:  bool — ttl_efficiency_pct < TTL_EFFICIENCY_FLOOR (70%)
//!
//! GossipTtlTrackerEntry (hash-chained):
//!   epoch_end:           u64
//!   expired_count:       u32
//!   delivered_count:     u32
//!   mean_hops_x10:       u32
//!   ttl_efficiency_pct:  u32
//!   low_efficiency:      bool
//!   entry_hash:          [u8;32]
//!   prev_hash:           [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ expired_count_be4
//!                       ‖ delivered_count_be4 ‖ mean_hops_x10_be4
//!                       ‖ ttl_efficiency_pct_be4 ‖ low_efficiency_byte)
//!
//! GossipTtlTrackerLog: record(epoch_end, expired, delivered, total_hops),
//!   total_expired(), total_delivered(), low_efficiency_count(),
//!   min_efficiency_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_TTL_TRACKER_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const TTL_EFFICIENCY_FLOOR: u32 = 70; // percent

// ─── GossipTtlTrackerEntry ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipTtlTrackerEntry {
    pub epoch_end:          u64,
    pub expired_count:      u32,
    pub delivered_count:    u32,
    pub mean_hops_x10:      u32,
    pub ttl_efficiency_pct: u32,
    pub low_efficiency:     bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_ttl_tracker_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    expired_count:      u32,
    delivered_count:    u32,
    mean_hops_x10:      u32,
    ttl_efficiency_pct: u32,
    low_efficiency:     bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(expired_count.to_be_bytes());
    h.update(delivered_count.to_be_bytes());
    h.update(mean_hops_x10.to_be_bytes());
    h.update(ttl_efficiency_pct.to_be_bytes());
    h.update([low_efficiency as u8]);
    h.finalize().into()
}

// ─── GossipTtlTrackerLog ──────────────────────────────────────────────────────

pub struct GossipTtlTrackerLog {
    entries: Vec<GossipTtlTrackerEntry>,
}

impl GossipTtlTrackerLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipTtlTrackerEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipTtlTrackerEntry> { self.entries.last() }

    /// Total expired messages across all epochs.
    pub fn total_expired(&self) -> u64 {
        self.entries.iter().map(|e| e.expired_count as u64).sum()
    }

    /// Total delivered messages across all epochs.
    pub fn total_delivered(&self) -> u64 {
        self.entries.iter().map(|e| e.delivered_count as u64).sum()
    }

    /// Count of epochs where low_efficiency == true.
    pub fn low_efficiency_count(&self) -> usize {
        self.entries.iter().filter(|e| e.low_efficiency).count()
    }

    /// Minimum ttl_efficiency_pct across all epochs. Returns 100 if empty.
    pub fn min_efficiency_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.ttl_efficiency_pct).min().unwrap_or(100)
    }

    /// Record TTL stats for one epoch.
    /// mean_hops_x10 = total_hops * 10 / max(delivered_count, 1).
    /// ttl_efficiency_pct = delivered * 100 / max(expired + delivered, 1).
    pub fn record(
        &mut self,
        epoch_end:       u64,
        expired_count:   u32,
        delivered_count: u32,
        total_hops:      u32,
    ) -> &GossipTtlTrackerEntry {
        let mean_hops_x10 = (total_hops as u64 * 10
            / delivered_count.max(1) as u64) as u32;
        let total = expired_count.saturating_add(delivered_count).max(1);
        let ttl_efficiency_pct = (delivered_count as u64 * 100 / total as u64) as u32;
        let low_efficiency = ttl_efficiency_pct < TTL_EFFICIENCY_FLOOR;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_TTL_TRACKER_GENESIS_HASH);

        let entry_hash = compute_ttl_tracker_hash(
            &prev, epoch_end, expired_count, delivered_count,
            mean_hops_x10, ttl_efficiency_pct, low_efficiency,
        );

        self.entries.push(GossipTtlTrackerEntry {
            epoch_end,
            expired_count,
            delivered_count,
            mean_hops_x10,
            ttl_efficiency_pct,
            low_efficiency,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_TTL_TRACKER_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_ttl_tracker_hash(
                &prev, e.epoch_end, e.expired_count, e.delivered_count,
                e.mean_hops_x10, e.ttl_efficiency_pct, e.low_efficiency,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipTtlTrackerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipTtlTrackerLog::new();
        // expired=10, delivered=90, total_hops=270
        let e = log.record(1, 10, 90, 270);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.expired_count, 10);
        assert_eq!(e.delivered_count, 90);
        // mean_hops_x10 = 270*10/90 = 30 (mean = 3.0)
        assert_eq!(e.mean_hops_x10, 30);
        // ttl_efficiency_pct = 90*100/100 = 90
        assert_eq!(e.ttl_efficiency_pct, 90);
    }

    #[test]
    fn zero_traffic_stored() {
        let mut log = GossipTtlTrackerLog::new();
        let e = log.record(1, 0, 0, 0);
        assert_eq!(e.mean_hops_x10, 0);
        assert_eq!(e.ttl_efficiency_pct, 0);
        assert!(e.low_efficiency);
    }

    #[test]
    fn all_delivered_full_efficiency() {
        let mut log = GossipTtlTrackerLog::new();
        let e = log.record(1, 0, 100, 300);
        assert_eq!(e.ttl_efficiency_pct, 100);
        assert!(!e.low_efficiency);
    }

    #[test]
    fn all_expired_zero_efficiency() {
        let mut log = GossipTtlTrackerLog::new();
        let e = log.record(1, 100, 0, 0);
        assert_eq!(e.ttl_efficiency_pct, 0);
        assert!(e.low_efficiency);
    }

    // ── mean_hops_x10 arithmetic ──────────────────────────────────────────────

    #[test]
    fn mean_hops_x10_rounds_down() {
        let mut log = GossipTtlTrackerLog::new();
        // total_hops=35, delivered=10 → 35*10/10 = 35 (mean = 3.5)
        let e = log.record(1, 5, 10, 35);
        assert_eq!(e.mean_hops_x10, 35);
        // total_hops=11, delivered=3 → 11*10/3 = 36 (mean = 3.666... rounds down)
        let e2 = log.record(2, 2, 3, 11);
        assert_eq!(e2.mean_hops_x10, 36);
    }

    // ── low_efficiency threshold ──────────────────────────────────────────────

    #[test]
    fn low_efficiency_below_floor() {
        let mut log = GossipTtlTrackerLog::new();
        // efficiency = 69% → low
        let e = log.record(1, 31, 69, 207);
        assert_eq!(e.ttl_efficiency_pct, 69);
        assert!(e.low_efficiency);
    }

    #[test]
    fn efficiency_at_floor_not_low() {
        let mut log = GossipTtlTrackerLog::new();
        // efficiency = 70% → exactly at floor, NOT low
        let e = log.record(1, 30, 70, 210);
        assert_eq!(e.ttl_efficiency_pct, 70);
        assert!(!e.low_efficiency);
    }

    #[test]
    fn high_efficiency_not_low() {
        let mut log = GossipTtlTrackerLog::new();
        let e = log.record(1, 5, 95, 285);
        assert!(!e.low_efficiency);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipTtlTrackerLog::new();
        log.record(1, 10, 90, 270);
        log.record(2, 5,  95, 285);
        log.record(3, 20, 80, 240);
        assert_eq!(log.total_expired(), 35);
        assert_eq!(log.total_delivered(), 265);
    }

    #[test]
    fn low_efficiency_count_correct() {
        let mut log = GossipTtlTrackerLog::new();
        log.record(1, 10, 90, 270); // 90% — ok
        log.record(2, 35, 65, 195); // 65% — low
        log.record(3, 5,  95, 285); // 95% — ok
        log.record(4, 40, 60, 180); // 60% — low
        assert_eq!(log.low_efficiency_count(), 2);
    }

    #[test]
    fn min_efficiency_pct_correct() {
        let mut log = GossipTtlTrackerLog::new();
        log.record(1, 5, 95, 285); // 95%
        log.record(2, 35, 65, 195); // 65%
        log.record(3, 15, 85, 255); // 85%
        assert_eq!(log.min_efficiency_pct(), 65);
    }

    #[test]
    fn min_efficiency_empty_is_100() {
        let log = GossipTtlTrackerLog::new();
        assert_eq!(log.min_efficiency_pct(), 100);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipTtlTrackerLog::new();
        let e = log.record(1, 10, 90, 270);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipTtlTrackerLog::new();
        let e = log.record(1, 10, 90, 270);
        assert_eq!(e.prev_hash, GOSSIP_TTL_TRACKER_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipTtlTrackerLog::new();
        log.record(1, 10, 90, 270);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 5, 95, 285);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipTtlTrackerLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipTtlTrackerLog::new();
        for i in 1u64..=5 {
            log.record(i, i as u32 * 5, 100 - i as u32 * 5, (100 - i as u32 * 5) * 3);
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipTtlTrackerLog::new();
        log.record(1, 10, 90, 270);
        log.record(2, 5, 95, 285);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipTtlTrackerLog::new();
        let mut l2 = GossipTtlTrackerLog::new();
        let h1 = l1.record(7, 15, 85, 255).entry_hash;
        let h2 = l2.record(7, 15, 85, 255).entry_hash;
        assert_eq!(h1, h2);
    }
}
