//! Gate 402 — Gossip Epoch Bandwidth Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch byte-level bandwidth accounting for the gossip layer.
//!   bytes_sent:     u64 — total bytes transmitted this epoch
//!   bytes_received: u64 — total bytes received this epoch
//!   bytes_overhead: u64 — retransmit + duplicate bytes (overhead traffic)
//!   overhead_pct:   u32 — bytes_overhead * 100 / max(bytes_sent + bytes_received, 1)
//!   high_overhead:  bool — overhead_pct >= BANDWIDTH_OVERHEAD_THRESHOLD (20%)
//!
//! GossipEpochBandwidthEntry (hash-chained):
//!   epoch_end:      u64
//!   bytes_sent:     u64
//!   bytes_received: u64
//!   bytes_overhead: u64
//!   overhead_pct:   u32
//!   high_overhead:  bool
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ bytes_sent_be8
//!                       ‖ bytes_received_be8 ‖ bytes_overhead_be8
//!                       ‖ overhead_pct_be4 ‖ high_overhead_byte)
//!
//! GossipEpochBandwidthLog: record(epoch_end, bytes_sent, bytes_received, bytes_overhead),
//!   total_sent(), total_received(), total_overhead(),
//!   high_overhead_count(), max_overhead_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_EPOCH_BANDWIDTH_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const BANDWIDTH_OVERHEAD_THRESHOLD: u32 = 20; // percent

// ─── GossipEpochBandwidthEntry ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochBandwidthEntry {
    pub epoch_end:      u64,
    pub bytes_sent:     u64,
    pub bytes_received: u64,
    pub bytes_overhead: u64,
    pub overhead_pct:   u32,
    pub high_overhead:  bool,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_epoch_bandwidth_hash(
    prev:           &[u8; 32],
    epoch_end:      u64,
    bytes_sent:     u64,
    bytes_received: u64,
    bytes_overhead: u64,
    overhead_pct:   u32,
    high_overhead:  bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(bytes_sent.to_be_bytes());
    h.update(bytes_received.to_be_bytes());
    h.update(bytes_overhead.to_be_bytes());
    h.update(overhead_pct.to_be_bytes());
    h.update([high_overhead as u8]);
    h.finalize().into()
}

// ─── GossipEpochBandwidthLog ──────────────────────────────────────────────────

pub struct GossipEpochBandwidthLog {
    entries: Vec<GossipEpochBandwidthEntry>,
}

impl GossipEpochBandwidthLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipEpochBandwidthEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipEpochBandwidthEntry> { self.entries.last() }

    /// Total bytes sent across all epochs.
    pub fn total_sent(&self) -> u64 {
        self.entries.iter().map(|e| e.bytes_sent).sum()
    }

    /// Total bytes received across all epochs.
    pub fn total_received(&self) -> u64 {
        self.entries.iter().map(|e| e.bytes_received).sum()
    }

    /// Total overhead bytes across all epochs.
    pub fn total_overhead(&self) -> u64 {
        self.entries.iter().map(|e| e.bytes_overhead).sum()
    }

    /// Count of epochs where high_overhead == true.
    pub fn high_overhead_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_overhead).count()
    }

    /// Maximum overhead_pct in a single epoch. Returns 0 if empty.
    pub fn max_overhead_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.overhead_pct).max().unwrap_or(0)
    }

    /// Record bandwidth stats for one epoch.
    /// overhead_pct = bytes_overhead * 100 / max(bytes_sent + bytes_received, 1).
    pub fn record(
        &mut self,
        epoch_end:      u64,
        bytes_sent:     u64,
        bytes_received: u64,
        bytes_overhead: u64,
    ) -> &GossipEpochBandwidthEntry {
        let total = bytes_sent.saturating_add(bytes_received).max(1);
        let overhead_pct = (bytes_overhead.saturating_mul(100) / total) as u32;
        let high_overhead = overhead_pct >= BANDWIDTH_OVERHEAD_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_EPOCH_BANDWIDTH_GENESIS_HASH);

        let entry_hash = compute_epoch_bandwidth_hash(
            &prev, epoch_end, bytes_sent, bytes_received,
            bytes_overhead, overhead_pct, high_overhead,
        );

        self.entries.push(GossipEpochBandwidthEntry {
            epoch_end,
            bytes_sent,
            bytes_received,
            bytes_overhead,
            overhead_pct,
            high_overhead,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_EPOCH_BANDWIDTH_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_epoch_bandwidth_hash(
                &prev, e.epoch_end, e.bytes_sent, e.bytes_received,
                e.bytes_overhead, e.overhead_pct, e.high_overhead,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochBandwidthLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipEpochBandwidthLog::new();
        let e = log.record(1, 1000, 2000, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.bytes_sent, 1000);
        assert_eq!(e.bytes_received, 2000);
        assert_eq!(e.bytes_overhead, 100);
        // overhead_pct = 100*100/3000 = 3
        assert_eq!(e.overhead_pct, 3);
    }

    #[test]
    fn zero_traffic_stored() {
        let mut log = GossipEpochBandwidthLog::new();
        let e = log.record(1, 0, 0, 0);
        assert_eq!(e.overhead_pct, 0);
        assert!(!e.high_overhead);
    }

    // ── overhead_pct arithmetic ───────────────────────────────────────────────

    #[test]
    fn overhead_pct_rounds_down() {
        let mut log = GossipEpochBandwidthLog::new();
        // overhead=199, total=1000 → 199*100/1000=19
        let e = log.record(1, 500, 500, 199);
        assert_eq!(e.overhead_pct, 19);
    }

    #[test]
    fn overhead_cannot_exceed_100_pct() {
        let mut log = GossipEpochBandwidthLog::new();
        // overhead > total (malformed but must not panic)
        let e = log.record(1, 100, 100, 300);
        // 300*100/200 = 150 — raw value; no cap applied in spec
        assert_eq!(e.overhead_pct, 150);
    }

    // ── high_overhead threshold ───────────────────────────────────────────────

    #[test]
    fn high_overhead_below_threshold() {
        let mut log = GossipEpochBandwidthLog::new();
        // 19% < 20% → not high
        let e = log.record(1, 500, 500, 190);
        assert_eq!(e.overhead_pct, 19);
        assert!(!e.high_overhead);
    }

    #[test]
    fn high_overhead_at_threshold() {
        let mut log = GossipEpochBandwidthLog::new();
        // 200*100/1000 = 20 → exactly at threshold
        let e = log.record(1, 500, 500, 200);
        assert_eq!(e.overhead_pct, 20);
        assert!(e.high_overhead);
    }

    #[test]
    fn high_overhead_above_threshold() {
        let mut log = GossipEpochBandwidthLog::new();
        let e = log.record(1, 500, 500, 400);
        assert!(e.high_overhead);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipEpochBandwidthLog::new();
        log.record(1, 1000, 2000, 100);
        log.record(2, 500,  1500,  50);
        log.record(3, 2000, 3000, 200);
        assert_eq!(log.total_sent(),     3500);
        assert_eq!(log.total_received(), 6500);
        assert_eq!(log.total_overhead(), 350);
    }

    #[test]
    fn high_overhead_count_correct() {
        let mut log = GossipEpochBandwidthLog::new();
        log.record(1, 500, 500, 190); // 19% — not high
        log.record(2, 500, 500, 200); // 20% — high
        log.record(3, 500, 500, 400); // 40% — high
        log.record(4, 500, 500, 100); // 10% — not high
        assert_eq!(log.high_overhead_count(), 2);
    }

    #[test]
    fn max_overhead_pct_correct() {
        let mut log = GossipEpochBandwidthLog::new();
        log.record(1, 500, 500, 100);  // 10%
        log.record(2, 500, 500, 400);  // 40%
        log.record(3, 500, 500, 200);  // 20%
        assert_eq!(log.max_overhead_pct(), 40);
    }

    #[test]
    fn max_overhead_pct_empty_zero() {
        let log = GossipEpochBandwidthLog::new();
        assert_eq!(log.max_overhead_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipEpochBandwidthLog::new();
        let e = log.record(1, 1000, 2000, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipEpochBandwidthLog::new();
        let e = log.record(1, 1000, 2000, 100);
        assert_eq!(e.prev_hash, GOSSIP_EPOCH_BANDWIDTH_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipEpochBandwidthLog::new();
        log.record(1, 1000, 2000, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 500, 1500, 50);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipEpochBandwidthLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipEpochBandwidthLog::new();
        for i in 1u64..=5 {
            log.record(i, i * 1000, i * 2000, i * 100);
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipEpochBandwidthLog::new();
        log.record(1, 1000, 2000, 100);
        log.record(2, 500,  1500, 50);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipEpochBandwidthLog::new();
        let mut l2 = GossipEpochBandwidthLog::new();
        let h1 = l1.record(5, 2000, 4000, 300).entry_hash;
        let h2 = l2.record(5, 2000, 4000, 300).entry_hash;
        assert_eq!(h1, h2);
    }
}
