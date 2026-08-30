//! Gate 404 — Gossip Queue Depth Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip send-queue depth samples. The queue depth is
//! sampled at epoch boundaries. High queue depth indicates the gossip layer
//! cannot drain messages fast enough.
//!
//! min_depth:  u32 — minimum sampled queue depth this epoch
//! max_depth:  u32 — maximum sampled queue depth this epoch
//! mean_depth: u32 — (min_depth + max_depth) / 2 (integer average of extremes)
//! queue_full: bool — max_depth >= QUEUE_FULL_THRESHOLD
//!
//! QUEUE_FULL_THRESHOLD: u32 = 1000
//!
//! GossipQueueDepthEntry (hash-chained):
//!   epoch_end:  u64
//!   min_depth:  u32
//!   max_depth:  u32
//!   mean_depth: u32
//!   queue_full: bool
//!   entry_hash: [u8;32]
//!   prev_hash:  [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ min_depth_be4
//!                       ‖ max_depth_be4 ‖ mean_depth_be4 ‖ queue_full_byte)
//!
//! GossipQueueDepthLog: record(epoch_end, min_depth, max_depth),
//!   queue_full_count(), max_ever_depth(), mean_of_means(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_QUEUE_DEPTH_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const QUEUE_FULL_THRESHOLD: u32 = 1000;

// ─── GossipQueueDepthEntry ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipQueueDepthEntry {
    pub epoch_end:  u64,
    pub min_depth:  u32,
    pub max_depth:  u32,
    pub mean_depth: u32,
    pub queue_full: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash:  [u8; 32],
}

fn compute_queue_depth_hash(
    prev:       &[u8; 32],
    epoch_end:  u64,
    min_depth:  u32,
    max_depth:  u32,
    mean_depth: u32,
    queue_full: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(min_depth.to_be_bytes());
    h.update(max_depth.to_be_bytes());
    h.update(mean_depth.to_be_bytes());
    h.update([queue_full as u8]);
    h.finalize().into()
}

// ─── GossipQueueDepthLog ──────────────────────────────────────────────────────

pub struct GossipQueueDepthLog {
    entries: Vec<GossipQueueDepthEntry>,
}

impl GossipQueueDepthLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipQueueDepthEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipQueueDepthEntry> { self.entries.last() }

    /// Count of epochs where queue_full == true.
    pub fn queue_full_count(&self) -> usize {
        self.entries.iter().filter(|e| e.queue_full).count()
    }

    /// Maximum max_depth ever recorded. Returns 0 if empty.
    pub fn max_ever_depth(&self) -> u32 {
        self.entries.iter().map(|e| e.max_depth).max().unwrap_or(0)
    }

    /// Integer mean of all per-epoch mean_depth values. Returns 0 if empty.
    pub fn mean_of_means(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.mean_depth as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record queue depth for one epoch.
    /// mean_depth = (min_depth + max_depth) / 2 (integer).
    /// queue_full = max_depth >= QUEUE_FULL_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end: u64,
        min_depth: u32,
        max_depth: u32,
    ) -> &GossipQueueDepthEntry {
        let mean_depth = min_depth.saturating_add(max_depth) / 2;
        let queue_full = max_depth >= QUEUE_FULL_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_QUEUE_DEPTH_GENESIS_HASH);

        let entry_hash = compute_queue_depth_hash(
            &prev, epoch_end, min_depth, max_depth, mean_depth, queue_full,
        );

        self.entries.push(GossipQueueDepthEntry {
            epoch_end,
            min_depth,
            max_depth,
            mean_depth,
            queue_full,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_QUEUE_DEPTH_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_queue_depth_hash(
                &prev, e.epoch_end, e.min_depth, e.max_depth,
                e.mean_depth, e.queue_full,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipQueueDepthLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipQueueDepthLog::new();
        let e = log.record(1, 100, 800);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.min_depth, 100);
        assert_eq!(e.max_depth, 800);
        assert_eq!(e.mean_depth, 450);
    }

    #[test]
    fn zero_depth_stored() {
        let mut log = GossipQueueDepthLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.mean_depth, 0);
        assert!(!e.queue_full);
    }

    #[test]
    fn mean_depth_rounds_down() {
        let mut log = GossipQueueDepthLog::new();
        // (100+201)/2 = 150 (rounds down)
        let e = log.record(1, 100, 201);
        assert_eq!(e.mean_depth, 150);
    }

    // ── queue_full threshold ──────────────────────────────────────────────────

    #[test]
    fn queue_full_below_threshold() {
        let mut log = GossipQueueDepthLog::new();
        let e = log.record(1, 0, QUEUE_FULL_THRESHOLD - 1);
        assert!(!e.queue_full);
    }

    #[test]
    fn queue_full_at_threshold() {
        let mut log = GossipQueueDepthLog::new();
        let e = log.record(1, 0, QUEUE_FULL_THRESHOLD);
        assert!(e.queue_full);
    }

    #[test]
    fn queue_full_above_threshold() {
        let mut log = GossipQueueDepthLog::new();
        let e = log.record(1, 500, QUEUE_FULL_THRESHOLD + 100);
        assert!(e.queue_full);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn queue_full_count_correct() {
        let mut log = GossipQueueDepthLog::new();
        log.record(1, 0, 500);  // not full
        log.record(2, 0, 1000); // full (at threshold)
        log.record(3, 0, 1500); // full
        log.record(4, 0, 200);  // not full
        assert_eq!(log.queue_full_count(), 2);
    }

    #[test]
    fn max_ever_depth_correct() {
        let mut log = GossipQueueDepthLog::new();
        log.record(1, 0, 500);
        log.record(2, 0, 1500);
        log.record(3, 0, 800);
        assert_eq!(log.max_ever_depth(), 1500);
    }

    #[test]
    fn max_ever_depth_empty_zero() {
        let log = GossipQueueDepthLog::new();
        assert_eq!(log.max_ever_depth(), 0);
    }

    #[test]
    fn mean_of_means_correct() {
        let mut log = GossipQueueDepthLog::new();
        log.record(1, 0, 200);   // mean=100
        log.record(2, 100, 500); // mean=300
        log.record(3, 200, 600); // mean=400
        // mean of means = (100+300+400)/3 = 266
        assert_eq!(log.mean_of_means(), 266);
    }

    #[test]
    fn mean_of_means_empty_zero() {
        let log = GossipQueueDepthLog::new();
        assert_eq!(log.mean_of_means(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipQueueDepthLog::new();
        let e = log.record(1, 100, 800);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipQueueDepthLog::new();
        let e = log.record(1, 100, 800);
        assert_eq!(e.prev_hash, GOSSIP_QUEUE_DEPTH_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipQueueDepthLog::new();
        log.record(1, 100, 800);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 200, 1200);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipQueueDepthLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipQueueDepthLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 50, i as u32 * 200); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipQueueDepthLog::new();
        log.record(1, 100, 800);
        log.record(2, 200, 1200);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipQueueDepthLog::new();
        let mut l2 = GossipQueueDepthLog::new();
        let h1 = l1.record(4, 200, 900).entry_hash;
        let h2 = l2.record(4, 200, 900).entry_hash;
        assert_eq!(h1, h2);
    }
}
