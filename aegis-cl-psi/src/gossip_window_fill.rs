//! Gate 412 — Gossip Window Fill Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip sliding window fill ratio. The window is a
//! fixed-capacity slot buffer; fill_ratio measures how full it was during the epoch.
//!
//! slots_used:    u32 — slots occupied at epoch end
//! slots_total:   u32 — total window capacity
//! fill_pct:      u32 — slots_used * 100 / max(slots_total, 1)
//! window_full:   bool — fill_pct >= WINDOW_FULL_THRESHOLD (90%)
//! window_empty:  bool — fill_pct == 0
//!
//! WINDOW_FULL_THRESHOLD: u32 = 90
//!
//! GossipWindowFillEntry (hash-chained):
//!   epoch_end:    u64
//!   slots_used:   u32
//!   slots_total:  u32
//!   fill_pct:     u32
//!   window_full:  bool
//!   window_empty: bool
//!   entry_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ slots_used_be4
//!                       ‖ slots_total_be4 ‖ fill_pct_be4
//!                       ‖ window_full_byte ‖ window_empty_byte)
//!
//! GossipWindowFillLog: record(epoch_end, slots_used, slots_total),
//!   full_count(), empty_count(), max_fill_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_WINDOW_FILL_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const WINDOW_FULL_THRESHOLD: u32 = 90; // percent

// ─── GossipWindowFillEntry ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipWindowFillEntry {
    pub epoch_end:    u64,
    pub slots_used:   u32,
    pub slots_total:  u32,
    pub fill_pct:     u32,
    pub window_full:  bool,
    pub window_empty: bool,
    pub entry_hash:   [u8; 32],
    pub prev_hash:    [u8; 32],
}

fn compute_window_fill_hash(
    prev:         &[u8; 32],
    epoch_end:    u64,
    slots_used:   u32,
    slots_total:  u32,
    fill_pct:     u32,
    window_full:  bool,
    window_empty: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(slots_used.to_be_bytes());
    h.update(slots_total.to_be_bytes());
    h.update(fill_pct.to_be_bytes());
    h.update([window_full as u8]);
    h.update([window_empty as u8]);
    h.finalize().into()
}

// ─── GossipWindowFillLog ──────────────────────────────────────────────────────

pub struct GossipWindowFillLog {
    entries: Vec<GossipWindowFillEntry>,
}

impl GossipWindowFillLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipWindowFillEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipWindowFillEntry> { self.entries.last() }

    /// Count of epochs where window_full == true.
    pub fn full_count(&self) -> usize {
        self.entries.iter().filter(|e| e.window_full).count()
    }

    /// Count of epochs where window_empty == true.
    pub fn empty_count(&self) -> usize {
        self.entries.iter().filter(|e| e.window_empty).count()
    }

    /// Maximum fill_pct in any epoch. Returns 0 if empty.
    pub fn max_fill_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.fill_pct).max().unwrap_or(0)
    }

    /// Record window fill state for one epoch.
    /// fill_pct = slots_used * 100 / max(slots_total, 1).
    /// window_full = fill_pct >= WINDOW_FULL_THRESHOLD.
    /// window_empty = fill_pct == 0.
    pub fn record(
        &mut self,
        epoch_end:   u64,
        slots_used:  u32,
        slots_total: u32,
    ) -> &GossipWindowFillEntry {
        let fill_pct = (slots_used as u64 * 100
            / slots_total.max(1) as u64) as u32;
        let window_full  = fill_pct >= WINDOW_FULL_THRESHOLD;
        let window_empty = fill_pct == 0;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_WINDOW_FILL_GENESIS_HASH);

        let entry_hash = compute_window_fill_hash(
            &prev, epoch_end, slots_used, slots_total,
            fill_pct, window_full, window_empty,
        );

        self.entries.push(GossipWindowFillEntry {
            epoch_end,
            slots_used,
            slots_total,
            fill_pct,
            window_full,
            window_empty,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_WINDOW_FILL_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_window_fill_hash(
                &prev, e.epoch_end, e.slots_used, e.slots_total,
                e.fill_pct, e.window_full, e.window_empty,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipWindowFillLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 70, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.slots_used, 70);
        assert_eq!(e.slots_total, 100);
        assert_eq!(e.fill_pct, 70);
    }

    #[test]
    fn zero_slots_stored() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.fill_pct, 0);
        assert!(!e.window_full);
        assert!(e.window_empty);
    }

    #[test]
    fn empty_window_detected() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 0, 100);
        assert_eq!(e.fill_pct, 0);
        assert!(e.window_empty);
    }

    #[test]
    fn non_empty_not_empty() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 1, 100);
        assert!(!e.window_empty);
    }

    #[test]
    fn fill_rounds_down() {
        let mut log = GossipWindowFillLog::new();
        // 89*100/101 = 88 (rounds down)
        let e = log.record(1, 89, 101);
        assert_eq!(e.fill_pct, 88);
    }

    // ── window_full threshold ─────────────────────────────────────────────────

    #[test]
    fn full_below_threshold() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 89, 100);
        assert_eq!(e.fill_pct, 89);
        assert!(!e.window_full);
    }

    #[test]
    fn full_at_threshold() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 90, 100);
        assert_eq!(e.fill_pct, 90);
        assert!(e.window_full);
    }

    #[test]
    fn full_above_threshold() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 95, 100);
        assert!(e.window_full);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn full_count_correct() {
        let mut log = GossipWindowFillLog::new();
        log.record(1, 70, 100); // 70% — not full
        log.record(2, 90, 100); // 90% — full
        log.record(3, 95, 100); // 95% — full
        log.record(4, 50, 100); // 50% — not full
        assert_eq!(log.full_count(), 2);
    }

    #[test]
    fn empty_count_correct() {
        let mut log = GossipWindowFillLog::new();
        log.record(1, 0, 100);  // empty
        log.record(2, 50, 100); // not empty
        log.record(3, 0, 100);  // empty
        assert_eq!(log.empty_count(), 2);
    }

    #[test]
    fn max_fill_pct_correct() {
        let mut log = GossipWindowFillLog::new();
        log.record(1, 70, 100);
        log.record(2, 95, 100);
        log.record(3, 80, 100);
        assert_eq!(log.max_fill_pct(), 95);
    }

    #[test]
    fn max_fill_empty_zero() {
        let log = GossipWindowFillLog::new();
        assert_eq!(log.max_fill_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 70, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipWindowFillLog::new();
        let e = log.record(1, 70, 100);
        assert_eq!(e.prev_hash, GOSSIP_WINDOW_FILL_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipWindowFillLog::new();
        log.record(1, 70, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 80, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipWindowFillLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipWindowFillLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 15, 100); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipWindowFillLog::new();
        log.record(1, 70, 100);
        log.record(2, 80, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipWindowFillLog::new();
        let mut l2 = GossipWindowFillLog::new();
        let h1 = l1.record(5, 75, 100).entry_hash;
        let h2 = l2.record(5, 75, 100).entry_hash;
        assert_eq!(h1, h2);
    }
}
