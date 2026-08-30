//! Gate 408 — Gossip Latency Histogram Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch message latency histogram with four buckets:
//!   fast_count:   u32 — messages with latency < 10 ms
//!   normal_count: u32 — latency 10–99 ms
//!   slow_count:   u32 — latency 100–499 ms
//!   stall_count:  u32 — latency ≥ 500 ms
//!
//! total_messages = fast + normal + slow + stall
//! stall_pct: u32 — stall_count * 100 / max(total_messages, 1)
//! degraded: bool — stall_pct >= STALL_DEGRADED_THRESHOLD (5%)
//!
//! STALL_DEGRADED_THRESHOLD: u32 = 5
//!
//! GossipLatencyHistogramEntry (hash-chained):
//!   epoch_end:    u64
//!   fast_count:   u32
//!   normal_count: u32
//!   slow_count:   u32
//!   stall_count:  u32
//!   stall_pct:    u32
//!   degraded:     bool
//!   entry_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ fast_be4 ‖ normal_be4
//!                       ‖ slow_be4 ‖ stall_be4 ‖ stall_pct_be4 ‖ degraded_byte)
//!
//! GossipLatencyHistogramLog:
//!   record(epoch_end, fast, normal, slow, stall),
//!   total_fast(), total_stall(), degraded_count(), max_stall_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_LATENCY_HISTOGRAM_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const STALL_DEGRADED_THRESHOLD: u32 = 5; // percent

// ─── GossipLatencyHistogramEntry ──────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipLatencyHistogramEntry {
    pub epoch_end:    u64,
    pub fast_count:   u32,
    pub normal_count: u32,
    pub slow_count:   u32,
    pub stall_count:  u32,
    pub stall_pct:    u32,
    pub degraded:     bool,
    pub entry_hash:   [u8; 32],
    pub prev_hash:    [u8; 32],
}

fn compute_latency_histogram_hash(
    prev:         &[u8; 32],
    epoch_end:    u64,
    fast_count:   u32,
    normal_count: u32,
    slow_count:   u32,
    stall_count:  u32,
    stall_pct:    u32,
    degraded:     bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(fast_count.to_be_bytes());
    h.update(normal_count.to_be_bytes());
    h.update(slow_count.to_be_bytes());
    h.update(stall_count.to_be_bytes());
    h.update(stall_pct.to_be_bytes());
    h.update([degraded as u8]);
    h.finalize().into()
}

// ─── GossipLatencyHistogramLog ────────────────────────────────────────────────

pub struct GossipLatencyHistogramLog {
    entries: Vec<GossipLatencyHistogramEntry>,
}

impl GossipLatencyHistogramLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipLatencyHistogramEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipLatencyHistogramEntry> { self.entries.last() }

    /// Total fast (<10ms) messages across all epochs.
    pub fn total_fast(&self) -> u64 {
        self.entries.iter().map(|e| e.fast_count as u64).sum()
    }

    /// Total stall (≥500ms) messages across all epochs.
    pub fn total_stall(&self) -> u64 {
        self.entries.iter().map(|e| e.stall_count as u64).sum()
    }

    /// Count of epochs where degraded == true.
    pub fn degraded_count(&self) -> usize {
        self.entries.iter().filter(|e| e.degraded).count()
    }

    /// Maximum stall_pct in any epoch. Returns 0 if empty.
    pub fn max_stall_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.stall_pct).max().unwrap_or(0)
    }

    /// Record latency histogram for one epoch.
    /// stall_pct = stall_count * 100 / max(fast+normal+slow+stall, 1).
    /// degraded = stall_pct >= STALL_DEGRADED_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:    u64,
        fast_count:   u32,
        normal_count: u32,
        slow_count:   u32,
        stall_count:  u32,
    ) -> &GossipLatencyHistogramEntry {
        let total = fast_count
            .saturating_add(normal_count)
            .saturating_add(slow_count)
            .saturating_add(stall_count)
            .max(1);
        let stall_pct = (stall_count as u64 * 100 / total as u64) as u32;
        let degraded = stall_pct >= STALL_DEGRADED_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_LATENCY_HISTOGRAM_GENESIS_HASH);

        let entry_hash = compute_latency_histogram_hash(
            &prev, epoch_end, fast_count, normal_count, slow_count,
            stall_count, stall_pct, degraded,
        );

        self.entries.push(GossipLatencyHistogramEntry {
            epoch_end,
            fast_count,
            normal_count,
            slow_count,
            stall_count,
            stall_pct,
            degraded,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_LATENCY_HISTOGRAM_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_latency_histogram_hash(
                &prev, e.epoch_end, e.fast_count, e.normal_count, e.slow_count,
                e.stall_count, e.stall_pct, e.degraded,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipLatencyHistogramLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipLatencyHistogramLog::new();
        // total = 500, stall_count = 10 → stall_pct = 2
        let e = log.record(1, 400, 80, 10, 10);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.fast_count, 400);
        assert_eq!(e.normal_count, 80);
        assert_eq!(e.slow_count, 10);
        assert_eq!(e.stall_count, 10);
        assert_eq!(e.stall_pct, 2);
    }

    #[test]
    fn zero_messages_stored() {
        let mut log = GossipLatencyHistogramLog::new();
        let e = log.record(1, 0, 0, 0, 0);
        assert_eq!(e.stall_pct, 0);
        assert!(!e.degraded);
    }

    #[test]
    fn all_stalled() {
        let mut log = GossipLatencyHistogramLog::new();
        let e = log.record(1, 0, 0, 0, 100);
        assert_eq!(e.stall_pct, 100);
        assert!(e.degraded);
    }

    #[test]
    fn stall_pct_rounds_down() {
        let mut log = GossipLatencyHistogramLog::new();
        // stall=4, total=101 → 4*100/101 = 3
        let e = log.record(1, 80, 17, 0, 4);
        assert_eq!(e.stall_pct, 3);
    }

    // ── degraded threshold ────────────────────────────────────────────────────

    #[test]
    fn degraded_below_threshold() {
        let mut log = GossipLatencyHistogramLog::new();
        // stall=4, total=100 → 4% < 5%
        let e = log.record(1, 90, 6, 0, 4);
        assert_eq!(e.stall_pct, 4);
        assert!(!e.degraded);
    }

    #[test]
    fn degraded_at_threshold() {
        let mut log = GossipLatencyHistogramLog::new();
        // stall=5, total=100 → 5% = threshold
        let e = log.record(1, 90, 5, 0, 5);
        assert_eq!(e.stall_pct, 5);
        assert!(e.degraded);
    }

    #[test]
    fn degraded_above_threshold() {
        let mut log = GossipLatencyHistogramLog::new();
        let e = log.record(1, 80, 10, 0, 10);
        assert!(e.degraded);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipLatencyHistogramLog::new();
        log.record(1, 400, 80, 10, 10);
        log.record(2, 300, 60, 20, 20);
        assert_eq!(log.total_fast(), 700);
        assert_eq!(log.total_stall(), 30);
    }

    #[test]
    fn degraded_count_correct() {
        let mut log = GossipLatencyHistogramLog::new();
        // total=100 each for clean percentages
        log.record(1, 90, 5, 1, 4);   // 4% — ok
        log.record(2, 400, 85, 5, 10); // 10/500=2% — ok
        log.record(3, 50,  30, 5, 15); // 15/100=15% — degraded
        log.record(4, 90,  4,  1, 5);  // 5/100=5% — degraded (at threshold)
        assert_eq!(log.degraded_count(), 2);
    }

    #[test]
    fn max_stall_pct_correct() {
        let mut log = GossipLatencyHistogramLog::new();
        log.record(1, 90, 5, 0, 5);  // 5%
        log.record(2, 70, 5, 0, 25); // 25%
        log.record(3, 85, 5, 0, 10); // 10%
        assert_eq!(log.max_stall_pct(), 25);
    }

    #[test]
    fn max_stall_pct_empty_zero() {
        let log = GossipLatencyHistogramLog::new();
        assert_eq!(log.max_stall_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipLatencyHistogramLog::new();
        let e = log.record(1, 400, 80, 10, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipLatencyHistogramLog::new();
        let e = log.record(1, 400, 80, 10, 10);
        assert_eq!(e.prev_hash, GOSSIP_LATENCY_HISTOGRAM_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipLatencyHistogramLog::new();
        log.record(1, 400, 80, 10, 10);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 300, 60, 20, 20);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipLatencyHistogramLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipLatencyHistogramLog::new();
        for i in 1u64..=5 {
            log.record(i, i as u32 * 80, i as u32 * 15, i as u32 * 3, i as u32 * 2);
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipLatencyHistogramLog::new();
        log.record(1, 400, 80, 10, 10);
        log.record(2, 300, 60, 20, 20);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipLatencyHistogramLog::new();
        let mut l2 = GossipLatencyHistogramLog::new();
        let h1 = l1.record(3, 300, 50, 8, 2).entry_hash;
        let h2 = l2.record(3, 300, 50, 8, 2).entry_hash;
        assert_eq!(h1, h2);
    }
}
