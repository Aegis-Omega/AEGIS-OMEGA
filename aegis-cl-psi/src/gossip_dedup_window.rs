//! Gate 399 — Gossip Deduplication Window Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of duplicate gossip messages detected. A duplicate is a
//! message whose ID was already seen earlier in the same epoch window.
//!
//! dup_ratio_pct = (dup_count * 100) / max(seen_count + dup_count, 1)
//!   (integer percent, rounds down).
//! high_dup = dup_ratio_pct >= DUP_SATURATION_THRESHOLD   (threshold = 25)
//!
//! GossipDedupWindowEntry (hash-chained):
//!   epoch_end:      u64
//!   seen_count:     u32  — unique messages processed this epoch
//!   dup_count:      u32  — duplicate messages detected this epoch
//!   dup_ratio_pct:  u32  — integer percent of total that were duplicates
//!   high_dup:       bool — dup_ratio_pct >= DUP_SATURATION_THRESHOLD
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ seen_count_be4 ‖ dup_count_be4
//!                       ‖ dup_ratio_pct_be4 ‖ high_dup_byte)
//!
//! GossipDedupWindowLog: record(epoch_end, seen_count, dup_count),
//!   total_seen(), total_dup(), high_dup_count(), max_dup_ratio_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_DEDUP_WINDOW_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const DUP_SATURATION_THRESHOLD: u32 = 25; // percent

// ─── GossipDedupWindowEntry ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDedupWindowEntry {
    pub epoch_end:     u64,
    pub seen_count:    u32,
    pub dup_count:     u32,
    pub dup_ratio_pct: u32,
    pub high_dup:      bool,
    pub entry_hash:    [u8; 32],
    pub prev_hash:     [u8; 32],
}

fn compute_dedup_window_hash(
    prev:          &[u8; 32],
    epoch_end:     u64,
    seen_count:    u32,
    dup_count:     u32,
    dup_ratio_pct: u32,
    high_dup:      bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(seen_count.to_be_bytes());
    h.update(dup_count.to_be_bytes());
    h.update(dup_ratio_pct.to_be_bytes());
    h.update([high_dup as u8]);
    h.finalize().into()
}

// ─── GossipDedupWindowLog ─────────────────────────────────────────────────────

pub struct GossipDedupWindowLog {
    entries: Vec<GossipDedupWindowEntry>,
}

impl GossipDedupWindowLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipDedupWindowEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipDedupWindowEntry> { self.entries.last() }

    /// Total unique messages seen across all epochs.
    pub fn total_seen(&self) -> u64 {
        self.entries.iter().map(|e| e.seen_count as u64).sum()
    }

    /// Total duplicate messages detected across all epochs.
    pub fn total_dup(&self) -> u64 {
        self.entries.iter().map(|e| e.dup_count as u64).sum()
    }

    /// Count of epochs where high_dup == true.
    pub fn high_dup_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_dup).count()
    }

    /// Maximum dup_ratio_pct in a single epoch. Returns 0 if empty.
    pub fn max_dup_ratio_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.dup_ratio_pct).max().unwrap_or(0)
    }

    /// Record deduplication stats for one epoch.
    /// dup_ratio_pct = (dup_count * 100) / max(seen_count + dup_count, 1).
    /// high_dup = dup_ratio_pct >= DUP_SATURATION_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:  u64,
        seen_count: u32,
        dup_count:  u32,
    ) -> &GossipDedupWindowEntry {
        let total = seen_count.saturating_add(dup_count).max(1);
        let dup_ratio_pct = (dup_count as u64 * 100 / total as u64) as u32;
        let high_dup = dup_ratio_pct >= DUP_SATURATION_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_DEDUP_WINDOW_GENESIS_HASH);

        let entry_hash = compute_dedup_window_hash(
            &prev, epoch_end, seen_count, dup_count, dup_ratio_pct, high_dup,
        );

        self.entries.push(GossipDedupWindowEntry {
            epoch_end,
            seen_count,
            dup_count,
            dup_ratio_pct,
            high_dup,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_DEDUP_WINDOW_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_dedup_window_hash(
                &prev, e.epoch_end, e.seen_count, e.dup_count,
                e.dup_ratio_pct, e.high_dup,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipDedupWindowLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipDedupWindowLog::new();
        let e = log.record(5, 75, 25);
        assert_eq!(e.epoch_end, 5);
        assert_eq!(e.seen_count, 75);
        assert_eq!(e.dup_count, 25);
        // dup_ratio_pct = 25*100/100 = 25
        assert_eq!(e.dup_ratio_pct, 25);
    }

    #[test]
    fn zero_traffic_stored() {
        let mut log = GossipDedupWindowLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.seen_count, 0);
        assert_eq!(e.dup_count, 0);
        // total = max(0+0, 1) = 1 → dup_ratio_pct = 0*100/1 = 0
        assert_eq!(e.dup_ratio_pct, 0);
        assert!(!e.high_dup);
    }

    #[test]
    fn all_duplicates() {
        let mut log = GossipDedupWindowLog::new();
        // seen=0, dup=100 → total=100, ratio=100*100/100=100%
        let e = log.record(1, 0, 100);
        assert_eq!(e.dup_ratio_pct, 100);
        assert!(e.high_dup);
    }

    #[test]
    fn no_duplicates() {
        let mut log = GossipDedupWindowLog::new();
        let e = log.record(1, 100, 0);
        assert_eq!(e.dup_ratio_pct, 0);
        assert!(!e.high_dup);
    }

    // ── dup_ratio_pct arithmetic ──────────────────────────────────────────────

    #[test]
    fn ratio_rounds_down() {
        let mut log = GossipDedupWindowLog::new();
        // seen=3, dup=1 → total=4, ratio=1*100/4=25
        let e = log.record(1, 3, 1);
        assert_eq!(e.dup_ratio_pct, 25);
        // seen=4, dup=1 → total=5, ratio=1*100/5=20
        let e2 = log.record(2, 4, 1);
        assert_eq!(e2.dup_ratio_pct, 20);
    }

    // ── high_dup threshold ────────────────────────────────────────────────────

    #[test]
    fn high_dup_below_threshold() {
        let mut log = GossipDedupWindowLog::new();
        // dup_ratio_pct = 24 → below threshold
        // seen=76, dup=24 → total=100, ratio=24
        let e = log.record(1, 76, 24);
        assert_eq!(e.dup_ratio_pct, 24);
        assert!(!e.high_dup);
    }

    #[test]
    fn high_dup_at_threshold() {
        let mut log = GossipDedupWindowLog::new();
        // dup_ratio_pct = 25 == threshold → high_dup
        let e = log.record(1, 75, 25);
        assert_eq!(e.dup_ratio_pct, 25);
        assert!(e.high_dup);
    }

    #[test]
    fn high_dup_above_threshold() {
        let mut log = GossipDedupWindowLog::new();
        let e = log.record(1, 50, 50);
        assert_eq!(e.dup_ratio_pct, 50);
        assert!(e.high_dup);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipDedupWindowLog::new();
        log.record(1, 80, 10);
        log.record(2, 70, 20);
        log.record(3, 60, 30);
        assert_eq!(log.total_seen(), 210);
        assert_eq!(log.total_dup(), 60);
    }

    #[test]
    fn high_dup_count_correct() {
        let mut log = GossipDedupWindowLog::new();
        log.record(1, 80, 10); // 10/90=11% — not high
        log.record(2, 75, 25); // 25/100=25% — high (at threshold)
        log.record(3, 50, 50); // 50/100=50% — high
        log.record(4, 90, 5);  // 5/95=5% — not high
        assert_eq!(log.high_dup_count(), 2);
    }

    #[test]
    fn max_dup_ratio_pct_correct() {
        let mut log = GossipDedupWindowLog::new();
        log.record(1, 75, 25); // 25%
        log.record(2, 50, 50); // 50%
        log.record(3, 80, 10); // ~11%
        assert_eq!(log.max_dup_ratio_pct(), 50);
    }

    #[test]
    fn max_dup_ratio_empty_zero() {
        let log = GossipDedupWindowLog::new();
        assert_eq!(log.max_dup_ratio_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipDedupWindowLog::new();
        let e = log.record(1, 80, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipDedupWindowLog::new();
        let e = log.record(1, 80, 10);
        assert_eq!(e.prev_hash, GOSSIP_DEDUP_WINDOW_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipDedupWindowLog::new();
        log.record(1, 80, 10);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 60, 30);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipDedupWindowLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipDedupWindowLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 10, i as u32 * 2); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipDedupWindowLog::new();
        log.record(1, 80, 10);
        log.record(2, 60, 30);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipDedupWindowLog::new();
        let mut l2 = GossipDedupWindowLog::new();
        let h1 = l1.record(7, 80, 20).entry_hash;
        let h2 = l2.record(7, 80, 20).entry_hash;
        assert_eq!(h1, h2);
    }
}
