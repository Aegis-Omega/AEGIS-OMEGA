//! Gate 406 — Gossip Message Size Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip message payload sizes in bytes.
//!
//! min_size:    u32 — smallest message seen this epoch
//! max_size:    u32 — largest message seen this epoch
//! mean_size:   u32 — (min_size + max_size) / 2 (integer average of extremes)
//! oversized:   bool — max_size >= OVERSIZE_THRESHOLD (65536 bytes = 64 KiB)
//!
//! OVERSIZE_THRESHOLD: u32 = 65536
//!
//! GossipMessageSizeEntry (hash-chained):
//!   epoch_end:   u64
//!   min_size:    u32
//!   max_size:    u32
//!   mean_size:   u32
//!   oversized:   bool
//!   entry_hash:  [u8;32]
//!   prev_hash:   [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ min_size_be4
//!                       ‖ max_size_be4 ‖ mean_size_be4 ‖ oversized_byte)
//!
//! GossipMessageSizeLog: record(epoch_end, min_size, max_size),
//!   oversized_count(), max_ever_size(), mean_of_means(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_MESSAGE_SIZE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const OVERSIZE_THRESHOLD: u32 = 65536; // 64 KiB

// ─── GossipMessageSizeEntry ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipMessageSizeEntry {
    pub epoch_end:  u64,
    pub min_size:   u32,
    pub max_size:   u32,
    pub mean_size:  u32,
    pub oversized:  bool,
    pub entry_hash: [u8; 32],
    pub prev_hash:  [u8; 32],
}

fn compute_message_size_hash(
    prev:      &[u8; 32],
    epoch_end: u64,
    min_size:  u32,
    max_size:  u32,
    mean_size: u32,
    oversized: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(min_size.to_be_bytes());
    h.update(max_size.to_be_bytes());
    h.update(mean_size.to_be_bytes());
    h.update([oversized as u8]);
    h.finalize().into()
}

// ─── GossipMessageSizeLog ─────────────────────────────────────────────────────

pub struct GossipMessageSizeLog {
    entries: Vec<GossipMessageSizeEntry>,
}

impl GossipMessageSizeLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipMessageSizeEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipMessageSizeEntry> { self.entries.last() }

    /// Count of epochs where oversized == true.
    pub fn oversized_count(&self) -> usize {
        self.entries.iter().filter(|e| e.oversized).count()
    }

    /// Maximum max_size ever recorded. Returns 0 if empty.
    pub fn max_ever_size(&self) -> u32 {
        self.entries.iter().map(|e| e.max_size).max().unwrap_or(0)
    }

    /// Integer mean of all per-epoch mean_size values. Returns 0 if empty.
    pub fn mean_of_means(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.mean_size as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record message size stats for one epoch.
    /// mean_size = (min_size + max_size) / 2 (integer).
    /// oversized = max_size >= OVERSIZE_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end: u64,
        min_size:  u32,
        max_size:  u32,
    ) -> &GossipMessageSizeEntry {
        let mean_size = min_size.saturating_add(max_size) / 2;
        let oversized = max_size >= OVERSIZE_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_MESSAGE_SIZE_GENESIS_HASH);

        let entry_hash = compute_message_size_hash(
            &prev, epoch_end, min_size, max_size, mean_size, oversized,
        );

        self.entries.push(GossipMessageSizeEntry {
            epoch_end,
            min_size,
            max_size,
            mean_size,
            oversized,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_MESSAGE_SIZE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_message_size_hash(
                &prev, e.epoch_end, e.min_size, e.max_size,
                e.mean_size, e.oversized,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipMessageSizeLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipMessageSizeLog::new();
        let e = log.record(1, 100, 1000);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.min_size, 100);
        assert_eq!(e.max_size, 1000);
        assert_eq!(e.mean_size, 550);
    }

    #[test]
    fn zero_sizes_stored() {
        let mut log = GossipMessageSizeLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.mean_size, 0);
        assert!(!e.oversized);
    }

    #[test]
    fn mean_rounds_down() {
        let mut log = GossipMessageSizeLog::new();
        // (100 + 201) / 2 = 150
        let e = log.record(1, 100, 201);
        assert_eq!(e.mean_size, 150);
    }

    // ── oversized threshold ───────────────────────────────────────────────────

    #[test]
    fn oversized_below_threshold() {
        let mut log = GossipMessageSizeLog::new();
        let e = log.record(1, 0, OVERSIZE_THRESHOLD - 1);
        assert!(!e.oversized);
    }

    #[test]
    fn oversized_at_threshold() {
        let mut log = GossipMessageSizeLog::new();
        let e = log.record(1, 0, OVERSIZE_THRESHOLD);
        assert!(e.oversized);
    }

    #[test]
    fn oversized_above_threshold() {
        let mut log = GossipMessageSizeLog::new();
        let e = log.record(1, 1000, OVERSIZE_THRESHOLD + 1024);
        assert!(e.oversized);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn oversized_count_correct() {
        let mut log = GossipMessageSizeLog::new();
        log.record(1, 0, 1000);          // not oversized
        log.record(2, 0, 65536);         // oversized (at threshold)
        log.record(3, 0, 100000);        // oversized
        log.record(4, 0, 500);           // not oversized
        assert_eq!(log.oversized_count(), 2);
    }

    #[test]
    fn max_ever_size_correct() {
        let mut log = GossipMessageSizeLog::new();
        log.record(1, 0, 1000);
        log.record(2, 0, 80000);
        log.record(3, 0, 2000);
        assert_eq!(log.max_ever_size(), 80000);
    }

    #[test]
    fn max_ever_size_empty_zero() {
        let log = GossipMessageSizeLog::new();
        assert_eq!(log.max_ever_size(), 0);
    }

    #[test]
    fn mean_of_means_correct() {
        let mut log = GossipMessageSizeLog::new();
        log.record(1, 0, 200);   // mean=100
        log.record(2, 100, 500); // mean=300
        log.record(3, 200, 600); // mean=400
        // (100 + 300 + 400) / 3 = 266
        assert_eq!(log.mean_of_means(), 266);
    }

    #[test]
    fn mean_of_means_empty_zero() {
        let log = GossipMessageSizeLog::new();
        assert_eq!(log.mean_of_means(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipMessageSizeLog::new();
        let e = log.record(1, 100, 1000);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipMessageSizeLog::new();
        let e = log.record(1, 100, 1000);
        assert_eq!(e.prev_hash, GOSSIP_MESSAGE_SIZE_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipMessageSizeLog::new();
        log.record(1, 100, 1000);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 200, 2000);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipMessageSizeLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipMessageSizeLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 100, i as u32 * 1000); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipMessageSizeLog::new();
        log.record(1, 100, 1000);
        log.record(2, 200, 2000);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipMessageSizeLog::new();
        let mut l2 = GossipMessageSizeLog::new();
        let h1 = l1.record(3, 512, 4096).entry_hash;
        let h2 = l2.record(3, 512, 4096).entry_hash;
        assert_eq!(h1, h2);
    }
}
