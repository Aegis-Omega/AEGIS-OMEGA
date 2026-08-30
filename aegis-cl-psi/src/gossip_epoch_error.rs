//! Gate 410 — Gossip Epoch Error Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip layer errors and exceptions.
//!
//! error_count:    u32 — total errors (decode failures, invalid messages, etc.)
//! warning_count:  u32 — total warnings (non-fatal anomalies)
//! total_events:   u32 — total gossip events processed this epoch
//! error_rate_pct: u32 — error_count * 100 / max(total_events, 1)
//! error_burst:    bool — error_rate_pct >= ERROR_BURST_THRESHOLD (2%)
//!
//! ERROR_BURST_THRESHOLD: u32 = 2
//!
//! GossipEpochErrorEntry (hash-chained):
//!   epoch_end:      u64
//!   error_count:    u32
//!   warning_count:  u32
//!   total_events:   u32
//!   error_rate_pct: u32
//!   error_burst:    bool
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ error_count_be4
//!                       ‖ warning_count_be4 ‖ total_events_be4
//!                       ‖ error_rate_pct_be4 ‖ error_burst_byte)
//!
//! GossipEpochErrorLog: record(epoch_end, error_count, warning_count, total_events),
//!   total_errors(), total_warnings(), burst_count(), max_error_rate_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_EPOCH_ERROR_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const ERROR_BURST_THRESHOLD: u32 = 2; // percent

// ─── GossipEpochErrorEntry ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochErrorEntry {
    pub epoch_end:      u64,
    pub error_count:    u32,
    pub warning_count:  u32,
    pub total_events:   u32,
    pub error_rate_pct: u32,
    pub error_burst:    bool,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_epoch_error_hash(
    prev:           &[u8; 32],
    epoch_end:      u64,
    error_count:    u32,
    warning_count:  u32,
    total_events:   u32,
    error_rate_pct: u32,
    error_burst:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(error_count.to_be_bytes());
    h.update(warning_count.to_be_bytes());
    h.update(total_events.to_be_bytes());
    h.update(error_rate_pct.to_be_bytes());
    h.update([error_burst as u8]);
    h.finalize().into()
}

// ─── GossipEpochErrorLog ──────────────────────────────────────────────────────

pub struct GossipEpochErrorLog {
    entries: Vec<GossipEpochErrorEntry>,
}

impl GossipEpochErrorLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipEpochErrorEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipEpochErrorEntry> { self.entries.last() }

    /// Total errors across all epochs.
    pub fn total_errors(&self) -> u64 {
        self.entries.iter().map(|e| e.error_count as u64).sum()
    }

    /// Total warnings across all epochs.
    pub fn total_warnings(&self) -> u64 {
        self.entries.iter().map(|e| e.warning_count as u64).sum()
    }

    /// Count of epochs where error_burst == true.
    pub fn burst_count(&self) -> usize {
        self.entries.iter().filter(|e| e.error_burst).count()
    }

    /// Maximum error_rate_pct in any epoch. Returns 0 if empty.
    pub fn max_error_rate_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.error_rate_pct).max().unwrap_or(0)
    }

    /// Record error stats for one epoch.
    /// error_rate_pct = error_count * 100 / max(total_events, 1).
    /// error_burst = error_rate_pct >= ERROR_BURST_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:     u64,
        error_count:   u32,
        warning_count: u32,
        total_events:  u32,
    ) -> &GossipEpochErrorEntry {
        let error_rate_pct = (error_count as u64 * 100
            / total_events.max(1) as u64) as u32;
        let error_burst = error_rate_pct >= ERROR_BURST_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_EPOCH_ERROR_GENESIS_HASH);

        let entry_hash = compute_epoch_error_hash(
            &prev, epoch_end, error_count, warning_count,
            total_events, error_rate_pct, error_burst,
        );

        self.entries.push(GossipEpochErrorEntry {
            epoch_end,
            error_count,
            warning_count,
            total_events,
            error_rate_pct,
            error_burst,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_EPOCH_ERROR_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_epoch_error_hash(
                &prev, e.epoch_end, e.error_count, e.warning_count,
                e.total_events, e.error_rate_pct, e.error_burst,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochErrorLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipEpochErrorLog::new();
        // error_count=5, total=500 → rate=1%
        let e = log.record(1, 5, 10, 500);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.error_count, 5);
        assert_eq!(e.warning_count, 10);
        assert_eq!(e.total_events, 500);
        assert_eq!(e.error_rate_pct, 1);
    }

    #[test]
    fn zero_events_stored() {
        let mut log = GossipEpochErrorLog::new();
        let e = log.record(1, 0, 0, 0);
        assert_eq!(e.error_rate_pct, 0);
        assert!(!e.error_burst);
    }

    #[test]
    fn all_errors() {
        let mut log = GossipEpochErrorLog::new();
        let e = log.record(1, 100, 0, 100);
        assert_eq!(e.error_rate_pct, 100);
        assert!(e.error_burst);
    }

    #[test]
    fn rate_rounds_down() {
        let mut log = GossipEpochErrorLog::new();
        // 1*100/101 = 0
        let e = log.record(1, 1, 0, 101);
        assert_eq!(e.error_rate_pct, 0);
    }

    // ── error_burst threshold ─────────────────────────────────────────────────

    #[test]
    fn no_burst_below_threshold() {
        let mut log = GossipEpochErrorLog::new();
        // 1*100/100 = 1% < 2%
        let e = log.record(1, 1, 5, 100);
        assert_eq!(e.error_rate_pct, 1);
        assert!(!e.error_burst);
    }

    #[test]
    fn burst_at_threshold() {
        let mut log = GossipEpochErrorLog::new();
        // 2*100/100 = 2% = threshold
        let e = log.record(1, 2, 5, 100);
        assert_eq!(e.error_rate_pct, 2);
        assert!(e.error_burst);
    }

    #[test]
    fn burst_above_threshold() {
        let mut log = GossipEpochErrorLog::new();
        let e = log.record(1, 10, 5, 100);
        assert!(e.error_burst);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipEpochErrorLog::new();
        log.record(1, 5, 10, 500);
        log.record(2, 3, 7,  300);
        log.record(3, 8, 2,  400);
        assert_eq!(log.total_errors(), 16);
        assert_eq!(log.total_warnings(), 19);
    }

    #[test]
    fn burst_count_correct() {
        let mut log = GossipEpochErrorLog::new();
        log.record(1, 1, 5, 100); // 1% — ok
        log.record(2, 2, 5, 100); // 2% — burst
        log.record(3, 5, 5, 100); // 5% — burst
        log.record(4, 1, 5, 200); // 0% — ok
        assert_eq!(log.burst_count(), 2);
    }

    #[test]
    fn max_error_rate_pct_correct() {
        let mut log = GossipEpochErrorLog::new();
        log.record(1, 1, 5, 100); // 1%
        log.record(2, 8, 5, 100); // 8%
        log.record(3, 3, 5, 100); // 3%
        assert_eq!(log.max_error_rate_pct(), 8);
    }

    #[test]
    fn max_error_rate_empty_zero() {
        let log = GossipEpochErrorLog::new();
        assert_eq!(log.max_error_rate_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipEpochErrorLog::new();
        let e = log.record(1, 5, 10, 500);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipEpochErrorLog::new();
        let e = log.record(1, 5, 10, 500);
        assert_eq!(e.prev_hash, GOSSIP_EPOCH_ERROR_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipEpochErrorLog::new();
        log.record(1, 5, 10, 500);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 3, 7, 300);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipEpochErrorLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipEpochErrorLog::new();
        for i in 1u64..=5 { log.record(i, i as u32, i as u32 * 2, i as u32 * 100); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipEpochErrorLog::new();
        log.record(1, 5, 10, 500);
        log.record(2, 3, 7, 300);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipEpochErrorLog::new();
        let mut l2 = GossipEpochErrorLog::new();
        let h1 = l1.record(6, 4, 8, 400).entry_hash;
        let h2 = l2.record(6, 4, 8, 400).entry_hash;
        assert_eq!(h1, h2);
    }
}
