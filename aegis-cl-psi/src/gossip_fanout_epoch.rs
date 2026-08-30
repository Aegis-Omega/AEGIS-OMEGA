//! Gate 401 — Gossip Fanout Epoch Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip fanout — how many peers each message was
//! forwarded to on average. Fanout drives network coverage vs. bandwidth cost.
//!
//! total_forwards:   u32 — total forward operations this epoch
//! total_messages:   u32 — distinct messages forwarded this epoch
//! mean_fanout_x100: u32 — (total_forwards * 100) / max(total_messages, 1)
//!   (integer, scaled by 100 to preserve two decimal places without floats).
//!   e.g. mean_fanout_x100 = 350 means mean fanout = 3.50 peers/message.
//! high_fanout: bool — mean_fanout_x100 >= FANOUT_HIGH_THRESHOLD (600 = 6.00)
//! low_fanout:  bool — mean_fanout_x100 <  FANOUT_LOW_THRESHOLD  (200 = 2.00)
//!
//! GossipFanoutEpochEntry (hash-chained):
//!   epoch_end:         u64
//!   total_forwards:    u32
//!   total_messages:    u32
//!   mean_fanout_x100:  u32
//!   high_fanout:       bool
//!   low_fanout:        bool
//!   entry_hash:        [u8;32]
//!   prev_hash:         [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ total_forwards_be4
//!                       ‖ total_messages_be4 ‖ mean_fanout_x100_be4
//!                       ‖ high_fanout_byte ‖ low_fanout_byte)
//!
//! GossipFanoutEpochLog: record(epoch_end, total_forwards, total_messages),
//!   total_forwards_all(), total_messages_all(), high_fanout_count(),
//!   low_fanout_count(), max_mean_fanout_x100(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_FANOUT_EPOCH_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const FANOUT_HIGH_THRESHOLD: u32 = 600; // mean_fanout_x100 >= 600 → high (≥ 6.00)
pub const FANOUT_LOW_THRESHOLD:  u32 = 200; // mean_fanout_x100 < 200 → low (< 2.00)

// ─── GossipFanoutEpochEntry ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFanoutEpochEntry {
    pub epoch_end:        u64,
    pub total_forwards:   u32,
    pub total_messages:   u32,
    pub mean_fanout_x100: u32,
    pub high_fanout:      bool,
    pub low_fanout:       bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_fanout_epoch_hash(
    prev:             &[u8; 32],
    epoch_end:        u64,
    total_forwards:   u32,
    total_messages:   u32,
    mean_fanout_x100: u32,
    high_fanout:      bool,
    low_fanout:       bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(total_forwards.to_be_bytes());
    h.update(total_messages.to_be_bytes());
    h.update(mean_fanout_x100.to_be_bytes());
    h.update([high_fanout as u8]);
    h.update([low_fanout as u8]);
    h.finalize().into()
}

// ─── GossipFanoutEpochLog ─────────────────────────────────────────────────────

pub struct GossipFanoutEpochLog {
    entries: Vec<GossipFanoutEpochEntry>,
}

impl GossipFanoutEpochLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipFanoutEpochEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipFanoutEpochEntry> { self.entries.last() }

    /// Total forward operations across all epochs.
    pub fn total_forwards_all(&self) -> u64 {
        self.entries.iter().map(|e| e.total_forwards as u64).sum()
    }

    /// Total distinct messages forwarded across all epochs.
    pub fn total_messages_all(&self) -> u64 {
        self.entries.iter().map(|e| e.total_messages as u64).sum()
    }

    /// Count of epochs where high_fanout == true.
    pub fn high_fanout_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_fanout).count()
    }

    /// Count of epochs where low_fanout == true.
    pub fn low_fanout_count(&self) -> usize {
        self.entries.iter().filter(|e| e.low_fanout).count()
    }

    /// Maximum mean_fanout_x100 across all epochs. Returns 0 if empty.
    pub fn max_mean_fanout_x100(&self) -> u32 {
        self.entries.iter().map(|e| e.mean_fanout_x100).max().unwrap_or(0)
    }

    /// Record fanout stats for one epoch.
    /// mean_fanout_x100 = total_forwards * 100 / max(total_messages, 1).
    pub fn record(
        &mut self,
        epoch_end:      u64,
        total_forwards: u32,
        total_messages: u32,
    ) -> &GossipFanoutEpochEntry {
        let denom = total_messages.max(1) as u64;
        let mean_fanout_x100 = (total_forwards as u64 * 100 / denom) as u32;
        let high_fanout = mean_fanout_x100 >= FANOUT_HIGH_THRESHOLD;
        let low_fanout  = mean_fanout_x100 < FANOUT_LOW_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_FANOUT_EPOCH_GENESIS_HASH);

        let entry_hash = compute_fanout_epoch_hash(
            &prev, epoch_end, total_forwards, total_messages,
            mean_fanout_x100, high_fanout, low_fanout,
        );

        self.entries.push(GossipFanoutEpochEntry {
            epoch_end,
            total_forwards,
            total_messages,
            mean_fanout_x100,
            high_fanout,
            low_fanout,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_FANOUT_EPOCH_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_fanout_epoch_hash(
                &prev, e.epoch_end, e.total_forwards, e.total_messages,
                e.mean_fanout_x100, e.high_fanout, e.low_fanout,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFanoutEpochLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipFanoutEpochLog::new();
        let e = log.record(1, 300, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.total_forwards, 300);
        assert_eq!(e.total_messages, 100);
        // mean_fanout_x100 = 300*100/100 = 300
        assert_eq!(e.mean_fanout_x100, 300);
    }

    #[test]
    fn zero_messages_denominator_is_one() {
        let mut log = GossipFanoutEpochLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.total_forwards, 0);
        assert_eq!(e.total_messages, 0);
        assert_eq!(e.mean_fanout_x100, 0);
        assert!(e.low_fanout);
        assert!(!e.high_fanout);
    }

    #[test]
    fn mean_fanout_rounds_down() {
        let mut log = GossipFanoutEpochLog::new();
        // 350 forwards / 100 messages → 3.50 → x100 = 350
        let e = log.record(1, 350, 100);
        assert_eq!(e.mean_fanout_x100, 350);
        // 7 forwards / 3 messages = 2.333... → x100 = 233
        let e2 = log.record(2, 7, 3);
        assert_eq!(e2.mean_fanout_x100, 233);
    }

    // ── high/low_fanout thresholds ────────────────────────────────────────────

    #[test]
    fn low_fanout_below_threshold() {
        let mut log = GossipFanoutEpochLog::new();
        // mean = 100 < 200 → low
        let e = log.record(1, 100, 100);
        assert_eq!(e.mean_fanout_x100, 100);
        assert!(e.low_fanout);
        assert!(!e.high_fanout);
    }

    #[test]
    fn normal_fanout_neither_flag() {
        let mut log = GossipFanoutEpochLog::new();
        // mean_x100 = 400 → neither low(<200) nor high(>=600)
        let e = log.record(1, 400, 100);
        assert_eq!(e.mean_fanout_x100, 400);
        assert!(!e.low_fanout);
        assert!(!e.high_fanout);
    }

    #[test]
    fn high_fanout_at_threshold() {
        let mut log = GossipFanoutEpochLog::new();
        // mean_x100 = 600 → exactly at high threshold
        let e = log.record(1, 600, 100);
        assert_eq!(e.mean_fanout_x100, 600);
        assert!(e.high_fanout);
        assert!(!e.low_fanout);
    }

    #[test]
    fn high_fanout_above_threshold() {
        let mut log = GossipFanoutEpochLog::new();
        let e = log.record(1, 1000, 100);
        assert!(e.high_fanout);
        assert!(!e.low_fanout);
    }

    #[test]
    fn low_fanout_at_boundary() {
        let mut log = GossipFanoutEpochLog::new();
        // mean_x100 = 199 → low; 200 → not low
        let e1 = log.record(1, 199, 100);
        assert!(e1.low_fanout);
        let e2 = log.record(2, 200, 100);
        assert!(!e2.low_fanout);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn totals_correct() {
        let mut log = GossipFanoutEpochLog::new();
        log.record(1, 300, 100);
        log.record(2, 500, 200);
        log.record(3, 200, 50);
        assert_eq!(log.total_forwards_all(), 1000);
        assert_eq!(log.total_messages_all(), 350);
    }

    #[test]
    fn high_and_low_counts() {
        let mut log = GossipFanoutEpochLog::new();
        log.record(1, 100, 100); // 100 → low
        log.record(2, 600, 100); // 600 → high
        log.record(3, 400, 100); // 400 → neither
        log.record(4, 800, 100); // 800 → high
        assert_eq!(log.high_fanout_count(), 2);
        assert_eq!(log.low_fanout_count(), 1);
    }

    #[test]
    fn max_mean_fanout_correct() {
        let mut log = GossipFanoutEpochLog::new();
        log.record(1, 300, 100);
        log.record(2, 800, 100);
        log.record(3, 500, 100);
        assert_eq!(log.max_mean_fanout_x100(), 800);
    }

    #[test]
    fn max_mean_fanout_empty_zero() {
        let log = GossipFanoutEpochLog::new();
        assert_eq!(log.max_mean_fanout_x100(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipFanoutEpochLog::new();
        let e = log.record(1, 300, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipFanoutEpochLog::new();
        let e = log.record(1, 300, 100);
        assert_eq!(e.prev_hash, GOSSIP_FANOUT_EPOCH_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipFanoutEpochLog::new();
        log.record(1, 300, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 500, 150);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipFanoutEpochLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipFanoutEpochLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 100, i as u32 * 30); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipFanoutEpochLog::new();
        log.record(1, 300, 100);
        log.record(2, 500, 150);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipFanoutEpochLog::new();
        let mut l2 = GossipFanoutEpochLog::new();
        let h1 = l1.record(3, 450, 90).entry_hash;
        let h2 = l2.record(3, 450, 90).entry_hash;
        assert_eq!(h1, h2);
    }
}
